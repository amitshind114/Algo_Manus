"""Read-only local paper-run evidence gate.

The gate records whether declared retained research, robustness, and current
control evidence is complete. It does not approve a paper proposal, evaluate
proposal-level risk, append a paper event, or call any broker/provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
import json
from typing import Protocol

from algo_manus.application.experiment_evidence import ExperimentEvidenceReadService
from algo_manus.application.paper_promotion import PaperResearchPromotionService
from algo_manus.application.robustness import (
    RobustnessEvidence,
    RobustnessEvidenceRepository,
    RobustnessGateState,
)
from algo_manus.domain.risk_controls import RiskControlSnapshot


class PaperRunEligibilityState(StrEnum):
    """Evidence-only gate state; neither state grants proposal or execution authority."""

    EVIDENCE_COMPLETE = "EVIDENCE_COMPLETE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class PaperRunEligibilityPolicy:
    """Declared maximum ages for retained research-only evidence references."""

    policy_version: str
    max_research_age: timedelta
    max_robustness_age: timedelta

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("paper-run eligibility policy version is required")
        if self.max_research_age <= timedelta(0) or self.max_robustness_age <= timedelta(0):
            raise ValueError("paper-run eligibility evidence ages must be positive")


@dataclass(frozen=True, slots=True)
class PaperRunEligibilityEvidence:
    """Immutable local evidence assessment; this is not a paper-run authorization."""

    evidence_id: str
    state: PaperRunEligibilityState
    batch_id: str
    instrument_id: str
    manifest_id: str | None
    dataset_id: str | None
    strategy_id: str | None
    strategy_version: str | None
    parameter_revision_id: str | None
    robustness_evidence_id: str | None
    policy_version: str
    central_policy_version: str
    kill_switch_change_id: str
    blocking_reasons: tuple[str, ...]
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.batch_id.strip() or not self.instrument_id.strip():
            raise ValueError("paper-run eligibility evidence identity is required")
        if not self.policy_version.strip() or not self.central_policy_version.strip() or not self.kill_switch_change_id.strip():
            raise ValueError("paper-run eligibility policy/control references are required")
        if self.evaluated_at.tzinfo is None:
            raise ValueError("paper-run eligibility evaluation time must be timezone-aware")
        if self.state is PaperRunEligibilityState.EVIDENCE_COMPLETE and self.blocking_reasons:
            raise ValueError("complete paper-run evidence cannot have blocking reasons")
        if self.state is PaperRunEligibilityState.BLOCKED and not self.blocking_reasons:
            raise ValueError("blocked paper-run evidence requires named blocking reasons")


class PaperRunEligibilityEvidenceRepository(Protocol):
    def save(self, evidence: PaperRunEligibilityEvidence) -> None: ...

    def get(self, evidence_id: str) -> PaperRunEligibilityEvidence | None: ...

    def list_recent(self, limit: int = 20) -> tuple[PaperRunEligibilityEvidence, ...]: ...


class LocalPaperRunEligibilityService:
    """Assess pre-paper evidence completeness without mutating research, risk, or paper state."""

    def __init__(
        self,
        research_evidence: ExperimentEvidenceReadService,
        promotion: PaperResearchPromotionService,
        robustness: RobustnessEvidenceRepository,
        repository: PaperRunEligibilityEvidenceRepository,
    ) -> None:
        self._research_evidence = research_evidence
        self._promotion = promotion
        self._robustness = robustness
        self._repository = repository

    def evaluate(
        self,
        *,
        batch_id: str,
        instrument_id: str,
        control_snapshot: RiskControlSnapshot,
        policy: PaperRunEligibilityPolicy,
        evaluated_at: datetime | None = None,
    ) -> PaperRunEligibilityEvidence:
        if not batch_id.strip() or not instrument_id.strip():
            raise ValueError("batch_id and instrument_id are required")
        moment = evaluated_at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")

        reasons: list[str] = []
        view = self._research_evidence.get(batch_id)
        promotion = self._promotion.resolve(batch_id=batch_id, instrument_id=instrument_id)
        manifest_id: str | None = None
        dataset_id: str | None = None
        strategy_id: str | None = None
        strategy_version: str | None = None
        parameter_revision_id: str | None = None
        robustness_evidence: RobustnessEvidence | None = None

        if view is None or promotion is None:
            reasons.append("RESEARCH_PROMOTION_EVIDENCE_MISSING")
        else:
            promotion_evidence, _validation = promotion
            manifest = view.manifest
            manifest_id = promotion_evidence.manifest_id
            dataset_id = promotion_evidence.dataset_id
            strategy_id = manifest.strategy_id
            strategy_version = manifest.strategy_version
            parameter_revision_id = manifest.parameter_revision_id
            if self._is_older_than(moment, manifest.information_cutoff, policy.max_research_age):
                reasons.append("RESEARCH_EVIDENCE_STALE")
            robustness_evidence, robustness_parameter_mismatch, candidate_history_insufficient = self._matching_robustness(
                dataset_id=dataset_id,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                parameter_revision_id=parameter_revision_id,
            )
            if robustness_evidence is None:
                reasons.append(
                    "ROBUSTNESS_PARAMETER_REVISION_MISMATCH"
                    if robustness_parameter_mismatch
                    else "ROBUSTNESS_EVIDENCE_MISSING"
                )
            elif candidate_history_insufficient or robustness_evidence.gate_state is RobustnessGateState.INSUFFICIENT_HISTORY:
                reasons.append("ROBUSTNESS_HISTORY_INSUFFICIENT")
            elif self._is_older_than(moment, robustness_evidence.created_at, policy.max_robustness_age):
                reasons.append("ROBUSTNESS_EVIDENCE_STALE")

        if control_snapshot.kill_switch_active:
            reasons.append("KILL_SWITCH_ACTIVE")

        evidence_id = self._evidence_id(
            batch_id=batch_id,
            instrument_id=instrument_id,
            manifest_id=manifest_id,
            dataset_id=dataset_id,
            parameter_revision_id=parameter_revision_id,
            robustness_evidence_id=robustness_evidence.evidence_id if robustness_evidence is not None else None,
            policy=policy,
            control_snapshot=control_snapshot,
            reasons=tuple(reasons),
            evaluated_at=moment,
        )
        existing = self._repository.get(evidence_id)
        if existing is not None:
            return existing
        evidence = PaperRunEligibilityEvidence(
            evidence_id=evidence_id,
            state=(PaperRunEligibilityState.BLOCKED if reasons else PaperRunEligibilityState.EVIDENCE_COMPLETE),
            batch_id=batch_id,
            instrument_id=instrument_id,
            manifest_id=manifest_id,
            dataset_id=dataset_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            parameter_revision_id=parameter_revision_id,
            robustness_evidence_id=robustness_evidence.evidence_id if robustness_evidence is not None else None,
            policy_version=policy.policy_version,
            central_policy_version=control_snapshot.policy.policy_version,
            kill_switch_change_id=control_snapshot.kill_switch_change.change_id,
            blocking_reasons=tuple(reasons),
            evaluated_at=moment,
        )
        self._repository.save(evidence)
        return evidence

    def _matching_robustness(
        self,
        *,
        dataset_id: str,
        strategy_id: str,
        strategy_version: str,
        parameter_revision_id: str,
    ) -> tuple[RobustnessEvidence | None, bool, bool]:
        parameter_mismatch = False
        for evidence in self._robustness.list_recent(limit=64):
            if (
                evidence.dataset_id == dataset_id
                and evidence.strategy_id == strategy_id
                and evidence.strategy_version == strategy_version
            ):
                candidate = next(
                    (item for item in evidence.candidates if item.parameter_revision_id == parameter_revision_id),
                    None,
                )
                if candidate is not None:
                    return evidence, False, candidate.status == "INSUFFICIENT_HISTORY"
                parameter_mismatch = True
        return None, parameter_mismatch, False

    @staticmethod
    def _is_older_than(moment: datetime, evidence_time: datetime, maximum_age: timedelta) -> bool:
        return moment > evidence_time and moment - evidence_time > maximum_age

    @staticmethod
    def _evidence_id(
        *,
        batch_id: str,
        instrument_id: str,
        manifest_id: str | None,
        dataset_id: str | None,
        parameter_revision_id: str | None,
        robustness_evidence_id: str | None,
        policy: PaperRunEligibilityPolicy,
        control_snapshot: RiskControlSnapshot,
        reasons: tuple[str, ...],
        evaluated_at: datetime,
    ) -> str:
        canonical = json.dumps(
            {
                "batch_id": batch_id,
                "instrument_id": instrument_id,
                "manifest_id": manifest_id,
                "dataset_id": dataset_id,
                "parameter_revision_id": parameter_revision_id,
                "robustness_evidence_id": robustness_evidence_id,
                "policy": {
                    "version": policy.policy_version,
                    "max_research_age_seconds": policy.max_research_age.total_seconds(),
                    "max_robustness_age_seconds": policy.max_robustness_age.total_seconds(),
                },
                "central_policy_version": control_snapshot.policy.policy_version,
                "kill_switch_change_id": control_snapshot.kill_switch_change.change_id,
                "blocking_reasons": reasons,
                "evaluated_at": evaluated_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"PEG-{sha256(canonical.encode()).hexdigest()[:20]}"
