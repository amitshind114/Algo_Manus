"""Local corporate-action and calendar review evidence gate.

This module records only a user-supplied local declaration about a dataset
review. It never retrieves corporate actions, calendars, prices, or broker data,
and it does not change validation, promotion, risk, paper, or execution state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
import json
from typing import Protocol

from algo_manus.domain.market_data import CandleDataset


class DatasetReviewDisposition(StrEnum):
    """Declared local review disposition; not a claim that a source is complete."""

    REVIEWED = "REVIEWED"
    UNRESOLVED = "UNRESOLVED"


class DatasetReviewGateState(StrEnum):
    """Informational review state with no research, paper, or execution authority."""

    REVIEW_COMPLETE = "REVIEW_COMPLETE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class LocalDatasetReviewPolicy:
    policy_version: str
    max_review_age: timedelta

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("dataset review policy version is required")
        if self.max_review_age <= timedelta(0):
            raise ValueError("dataset review maximum age must be positive")


@dataclass(frozen=True, slots=True)
class DatasetReviewDeclaration:
    """One bounded local declaration for a review category and candle-time scope."""

    disposition: DatasetReviewDisposition
    scope_start: datetime
    scope_end: datetime
    source_reference: str
    reviewed_at: datetime
    note: str

    def __post_init__(self) -> None:
        if self.scope_start.tzinfo is None or self.scope_end.tzinfo is None or self.reviewed_at.tzinfo is None:
            raise ValueError("dataset review declaration timestamps must be timezone-aware")
        if self.scope_start > self.scope_end:
            raise ValueError("dataset review scope start cannot be after scope end")
        if not self.source_reference.strip() or not self.note.strip():
            raise ValueError("dataset review declaration source reference and note are required")


@dataclass(frozen=True, slots=True)
class DatasetReviewEvidence:
    """Immutable local review evidence for one retained candle dataset."""

    evidence_id: str
    state: DatasetReviewGateState
    dataset_id: str
    instrument_id: str
    interval: str
    provenance_raw_content_sha256: str
    adjustment_basis: str
    corporate_action_review: DatasetReviewDeclaration | None
    calendar_review: DatasetReviewDeclaration | None
    policy_version: str
    blocking_reasons: tuple[str, ...]
    evaluated_at: datetime

    def __post_init__(self) -> None:
        required = {
            "evidence_id": self.evidence_id,
            "dataset_id": self.dataset_id,
            "instrument_id": self.instrument_id,
            "interval": self.interval,
            "provenance_raw_content_sha256": self.provenance_raw_content_sha256,
            "adjustment_basis": self.adjustment_basis,
            "policy_version": self.policy_version,
        }
        if any(not value.strip() for value in required.values()):
            raise ValueError("dataset review evidence identity and lineage are required")
        if self.evaluated_at.tzinfo is None:
            raise ValueError("dataset review evidence evaluation time must be timezone-aware")
        if self.state is DatasetReviewGateState.REVIEW_COMPLETE and self.blocking_reasons:
            raise ValueError("complete dataset review evidence cannot have blockers")
        if self.state is DatasetReviewGateState.BLOCKED and not self.blocking_reasons:
            raise ValueError("blocked dataset review evidence requires named blockers")


class DatasetReviewEvidenceRepository(Protocol):
    def save(self, evidence: DatasetReviewEvidence) -> None: ...

    def get(self, evidence_id: str) -> DatasetReviewEvidence | None: ...

    def list_recent(self, limit: int = 20) -> tuple[DatasetReviewEvidence, ...]: ...


class LocalDatasetReviewGateService:
    """Evaluate declared local review coverage without fetching or mutating any dataset."""

    def __init__(self, repository: DatasetReviewEvidenceRepository) -> None:
        self._repository = repository

    def evaluate(
        self,
        *,
        dataset: CandleDataset,
        corporate_action_review: DatasetReviewDeclaration | None,
        calendar_review: DatasetReviewDeclaration | None,
        policy: LocalDatasetReviewPolicy,
        evaluated_at: datetime | None = None,
    ) -> DatasetReviewEvidence:
        if dataset.provenance.use_case.value != "RESEARCH":
            raise ValueError("dataset review requires a research-use retained dataset")
        moment = evaluated_at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("dataset review evaluation time must be timezone-aware")
        scope_start = dataset.candles[0].timestamp
        scope_end = dataset.candles[-1].timestamp
        reasons = [
            *self._review_reasons(
                prefix="CORPORATE_ACTION",
                declaration=corporate_action_review,
                dataset_start=scope_start,
                dataset_end=scope_end,
                policy=policy,
                evaluated_at=moment,
            ),
            *self._review_reasons(
                prefix="CALENDAR",
                declaration=calendar_review,
                dataset_start=scope_start,
                dataset_end=scope_end,
                policy=policy,
                evaluated_at=moment,
            ),
        ]
        evidence_id = self._evidence_id(
            dataset=dataset,
            corporate_action_review=corporate_action_review,
            calendar_review=calendar_review,
            policy=policy,
            blocking_reasons=tuple(reasons),
            evaluated_at=moment,
        )
        existing = self._repository.get(evidence_id)
        if existing is not None:
            return existing
        evidence = DatasetReviewEvidence(
            evidence_id=evidence_id,
            state=DatasetReviewGateState.BLOCKED if reasons else DatasetReviewGateState.REVIEW_COMPLETE,
            dataset_id=dataset.dataset_id,
            instrument_id=dataset.instrument_id,
            interval=dataset.interval,
            provenance_raw_content_sha256=dataset.provenance.raw_content_sha256,
            adjustment_basis=dataset.provenance.adjustment_basis,
            corporate_action_review=corporate_action_review,
            calendar_review=calendar_review,
            policy_version=policy.policy_version,
            blocking_reasons=tuple(reasons),
            evaluated_at=moment,
        )
        self._repository.save(evidence)
        return evidence

    @staticmethod
    def _review_reasons(
        *,
        prefix: str,
        declaration: DatasetReviewDeclaration | None,
        dataset_start: datetime,
        dataset_end: datetime,
        policy: LocalDatasetReviewPolicy,
        evaluated_at: datetime,
    ) -> tuple[str, ...]:
        if declaration is None:
            return (f"{prefix}_REVIEW_MISSING",)
        reasons: list[str] = []
        if declaration.disposition is DatasetReviewDisposition.UNRESOLVED:
            reasons.append(f"{prefix}_REVIEW_UNRESOLVED")
        if declaration.scope_start > dataset_start or declaration.scope_end < dataset_end:
            reasons.append(f"{prefix}_REVIEW_SCOPE_INCOMPLETE")
        if declaration.reviewed_at > evaluated_at:
            reasons.append(f"{prefix}_REVIEW_TIME_AFTER_ASSESSMENT")
        elif evaluated_at - declaration.reviewed_at > policy.max_review_age:
            reasons.append(f"{prefix}_REVIEW_STALE")
        return tuple(reasons)

    @staticmethod
    def _evidence_id(
        *,
        dataset: CandleDataset,
        corporate_action_review: DatasetReviewDeclaration | None,
        calendar_review: DatasetReviewDeclaration | None,
        policy: LocalDatasetReviewPolicy,
        blocking_reasons: tuple[str, ...],
        evaluated_at: datetime,
    ) -> str:
        def review_payload(declaration: DatasetReviewDeclaration | None) -> dict[str, str] | None:
            if declaration is None:
                return None
            return {
                "disposition": declaration.disposition.value,
                "scope_start": declaration.scope_start.isoformat(),
                "scope_end": declaration.scope_end.isoformat(),
                "source_reference": declaration.source_reference,
                "reviewed_at": declaration.reviewed_at.isoformat(),
                "note": declaration.note,
            }

        canonical = json.dumps(
            {
                "dataset_id": dataset.dataset_id,
                "instrument_id": dataset.instrument_id,
                "interval": dataset.interval,
                "raw_content_sha256": dataset.provenance.raw_content_sha256,
                "adjustment_basis": dataset.provenance.adjustment_basis,
                "corporate_action_review": review_payload(corporate_action_review),
                "calendar_review": review_payload(calendar_review),
                "policy_version": policy.policy_version,
                "max_review_age_seconds": policy.max_review_age.total_seconds(),
                "blocking_reasons": blocking_reasons,
                "evaluated_at": evaluated_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"DREV-{sha256(canonical.encode()).hexdigest()[:20]}"
