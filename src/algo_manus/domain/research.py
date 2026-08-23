"""Immutable research-run evidence, data lineage and validation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Protocol

from algo_manus.domain.market_data import CandleDataset, DataSourceKind, DataUseCase


class DataValidationStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"


class DataValidationSeverity(StrEnum):
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class DataValidationIssue:
    """One named data-quality finding retained with a validation outcome."""

    code: str
    severity: DataValidationSeverity
    message: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ValueError("data validation issue code and message are required")


@dataclass(frozen=True, slots=True)
class DatasetValidationOutcome:
    """An immutable validation result; data may not be silently promoted on failure."""

    dataset_id: str
    status: DataValidationStatus
    policy_version: str
    validated_at: datetime
    issues: tuple[DataValidationIssue, ...] = ()

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.policy_version.strip():
            raise ValueError("dataset ID and validation policy version are required")
        if self.validated_at.tzinfo is None:
            raise ValueError("validation timestamp must be timezone-aware")
        has_error = any(issue.severity is DataValidationSeverity.ERROR for issue in self.issues)
        if self.status is DataValidationStatus.ACCEPTED and has_error:
            raise ValueError("accepted dataset validation cannot contain error issues")
        if self.status is not DataValidationStatus.ACCEPTED and not self.issues:
            raise ValueError("quarantined or rejected validation needs one or more issues")

    @property
    def research_eligible(self) -> bool:
        return self.status is DataValidationStatus.ACCEPTED


@dataclass(frozen=True, slots=True)
class DatasetLineage:
    """The stable, display-safe source evidence needed to reproduce one dataset."""

    dataset_id: str
    instrument_id: str
    interval: str
    source_name: str
    source_kind: DataSourceKind
    source_uri: str
    retrieved_at: datetime
    raw_content_sha256: str
    adjustment_basis: str
    use_case: DataUseCase

    def __post_init__(self) -> None:
        required = {
            "dataset_id": self.dataset_id,
            "instrument_id": self.instrument_id,
            "interval": self.interval,
            "source_name": self.source_name,
            "source_uri": self.source_uri,
            "adjustment_basis": self.adjustment_basis,
        }
        if any(not value.strip() for value in required.values()):
            raise ValueError("dataset lineage requires non-empty identity and source fields")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("dataset lineage retrieval time must be timezone-aware")
        if len(self.raw_content_sha256) != 64:
            raise ValueError("dataset lineage raw_content_sha256 must be a SHA-256 hex digest")

    @classmethod
    def from_dataset(cls, dataset: CandleDataset) -> "DatasetLineage":
        """Pin only accepted dataset/provenance facts into a research manifest."""

        provenance = dataset.provenance
        return cls(
            dataset_id=dataset.dataset_id,
            instrument_id=dataset.instrument_id,
            interval=dataset.interval,
            source_name=provenance.source_name,
            source_kind=provenance.source_kind,
            source_uri=provenance.source_uri,
            retrieved_at=provenance.retrieved_at,
            raw_content_sha256=provenance.raw_content_sha256,
            adjustment_basis=provenance.adjustment_basis,
            use_case=provenance.use_case,
        )


@dataclass(frozen=True, slots=True)
class ResearchExecutionAssumptions:
    """Versioned deterministic simulation inputs shared by a research run."""

    initial_cash: float
    quantity: int
    commission_bps: float
    slippage_bps: float
    force_close_at_end: bool = True
    execution_timing: str = "next_bar_open"

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_cash", float(self.initial_cash))
        object.__setattr__(self, "quantity", int(self.quantity))
        object.__setattr__(self, "commission_bps", float(self.commission_bps))
        object.__setattr__(self, "slippage_bps", float(self.slippage_bps))
        object.__setattr__(self, "force_close_at_end", bool(self.force_close_at_end))
        if self.initial_cash <= 0 or self.quantity <= 0:
            raise ValueError("initial_cash and quantity must be positive")
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("commission_bps and slippage_bps cannot be negative")
        if not self.execution_timing.strip():
            raise ValueError("execution timing is required")


@dataclass(frozen=True, slots=True)
class ResearchRunManifest:
    """Immutable and reproducible evidence record for a multi-security research run."""

    universe_id: str
    universe_snapshot_id: str
    strategy_id: str
    strategy_version: str
    parameter_revision_id: str
    engine_version: str
    lineages: tuple[DatasetLineage, ...]
    validation_outcomes: tuple[DatasetValidationOutcome, ...]
    execution_assumptions: ResearchExecutionAssumptions
    start: datetime
    end: datetime
    information_cutoff: datetime
    created_at: datetime
    git_commit_sha: str | None = None

    def __post_init__(self) -> None:
        required = {
            "universe_id": self.universe_id,
            "universe_snapshot_id": self.universe_snapshot_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "parameter_revision_id": self.parameter_revision_id,
            "engine_version": self.engine_version,
        }
        if any(not value.strip() for value in required.values()):
            raise ValueError("research manifest identity fields are required")
        if not self.lineages:
            raise ValueError("research manifest requires at least one dataset lineage")
        if self.start.tzinfo is None or self.end.tzinfo is None or self.information_cutoff.tzinfo is None or self.created_at.tzinfo is None:
            raise ValueError("research manifest timestamps must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("research manifest start must be before end")
        if self.information_cutoff > self.end:
            raise ValueError("information cutoff cannot be after the research end")
        if self.git_commit_sha is not None and not re.fullmatch(r"[0-9a-f]{7,64}", self.git_commit_sha):
            raise ValueError("git_commit_sha must be a lowercase hexadecimal commit identifier")
        lineage_ids = {lineage.dataset_id for lineage in self.lineages}
        if len(lineage_ids) != len(self.lineages):
            raise ValueError("research manifest cannot contain duplicate dataset lineages")
        if any(lineage.use_case is not DataUseCase.RESEARCH for lineage in self.lineages):
            raise ValueError("research manifest accepts only research-use datasets")
        outcomes_by_dataset = {outcome.dataset_id: outcome for outcome in self.validation_outcomes}
        if set(outcomes_by_dataset) != lineage_ids or len(outcomes_by_dataset) != len(self.validation_outcomes):
            raise ValueError("research manifest needs exactly one validation outcome per dataset")
        if any(not outcomes_by_dataset[lineage.dataset_id].research_eligible for lineage in self.lineages):
            raise ValueError("research manifest cannot include quarantined or rejected datasets")

    @property
    def manifest_id(self) -> str:
        """Deterministic identity for all reproducibility-relevant research inputs."""

        canonical = {
            "universe_id": self.universe_id,
            "universe_snapshot_id": self.universe_snapshot_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "parameter_revision_id": self.parameter_revision_id,
            "engine_version": self.engine_version,
            "lineages": [
                {
                    "dataset_id": item.dataset_id,
                    "instrument_id": item.instrument_id,
                    "interval": item.interval,
                    "source_name": item.source_name,
                    "source_kind": item.source_kind.value,
                    "source_uri": item.source_uri,
                    "retrieved_at": item.retrieved_at.isoformat(),
                    "raw_content_sha256": item.raw_content_sha256,
                    "adjustment_basis": item.adjustment_basis,
                    "use_case": item.use_case.value,
                }
                for item in sorted(self.lineages, key=lambda lineage: lineage.dataset_id)
            ],
            "validation": [
                {
                    "dataset_id": item.dataset_id,
                    "status": item.status.value,
                    "policy_version": item.policy_version,
                    "issues": [
                        {"code": issue.code, "severity": issue.severity.value, "message": issue.message}
                        for issue in item.issues
                    ],
                }
                for item in sorted(self.validation_outcomes, key=lambda outcome: outcome.dataset_id)
            ],
            "execution_assumptions": {
                "initial_cash": self.execution_assumptions.initial_cash,
                "quantity": self.execution_assumptions.quantity,
                "commission_bps": self.execution_assumptions.commission_bps,
                "slippage_bps": self.execution_assumptions.slippage_bps,
                "force_close_at_end": self.execution_assumptions.force_close_at_end,
                "execution_timing": self.execution_assumptions.execution_timing,
            },
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "information_cutoff": self.information_cutoff.isoformat(),
            "git_commit_sha": self.git_commit_sha,
        }
        digest = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return f"RUN-{digest[:20]}"


class ResearchRunManifestRepository(Protocol):
    """Persistence boundary for immutable research evidence records."""

    def save(self, manifest: ResearchRunManifest) -> None: ...

    def get(self, manifest_id: str) -> ResearchRunManifest | None: ...

    def list_recent(self, limit: int = 20) -> tuple[ResearchRunManifest, ...]: ...


class DatasetValidationRepository(Protocol):
    """Persistence boundary for immutable data-quality outcomes."""

    def save(self, outcome: DatasetValidationOutcome) -> None: ...

    def get(self, dataset_id: str, policy_version: str) -> DatasetValidationOutcome | None: ...
