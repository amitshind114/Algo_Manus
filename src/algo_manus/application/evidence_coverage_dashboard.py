"""Read-only freshness and cross-evidence coverage aggregation.

This module only reads retained local evidence. It does not fetch data, create
evidence, change a gate, or authorize research, paper, broker, or execution work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Protocol

from algo_manus.application.cross_evidence_linkage import (
    CrossEvidenceLinkageState,
    LocalCrossEvidenceLinkageReadService,
)
from algo_manus.application.dataset_review_gate import DatasetReviewEvidence, DatasetReviewGateState
from algo_manus.application.paper_run_eligibility import PaperRunEligibilityEvidence, PaperRunEligibilityState
from algo_manus.application.robustness import RobustnessEvidence


class EvidenceFreshness(StrEnum):
    """Read-time age interpretation, not a validation or promotion decision."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessCoveragePolicy:
    """One declared age limit for the display-only evidence coverage view."""

    policy_version: str
    maximum_evidence_age: timedelta

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("evidence coverage policy version is required")
        if self.maximum_evidence_age <= timedelta(0):
            raise ValueError("evidence coverage maximum age must be positive")


@dataclass(frozen=True, slots=True)
class EvidenceCoverageSummary:
    paper_total_count: int
    paper_current_count: int
    paper_stale_count: int
    paper_blocked_count: int
    robustness_total_count: int
    robustness_current_count: int
    robustness_stale_count: int
    robustness_missing_count: int
    review_total_count: int
    review_current_count: int
    review_stale_count: int
    review_blocked_count: int
    review_missing_count: int
    exact_link_complete_count: int
    exact_link_blocked_count: int
    lineage_mismatch_count: int


@dataclass(frozen=True, slots=True)
class EvidenceCoverageRow:
    paper_run_evidence_id: str
    batch_id: str
    instrument_id: str
    dataset_id: str | None
    paper_state: str
    paper_freshness: EvidenceFreshness
    robustness_evidence_id: str | None
    robustness_freshness: EvidenceFreshness
    dataset_review_evidence_id: str | None
    dataset_review_freshness: EvidenceFreshness
    linkage_state: str
    conditions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessCoverageDashboard:
    policy_version: str
    evaluated_at: datetime
    summary: EvidenceCoverageSummary
    rows: tuple[EvidenceCoverageRow, ...]

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("evidence coverage policy version is required")
        if self.evaluated_at.tzinfo is None:
            raise ValueError("evidence coverage evaluation time must be timezone-aware")


class RobustnessEvidenceReadRepository(Protocol):
    def get(self, evidence_id: str) -> RobustnessEvidence | None: ...

    def list_recent(self, limit: int = 20) -> tuple[RobustnessEvidence, ...]: ...


class PaperRunEvidenceReadRepository(Protocol):
    def get(self, evidence_id: str) -> PaperRunEligibilityEvidence | None: ...

    def list_recent(self, limit: int = 20) -> tuple[PaperRunEligibilityEvidence, ...]: ...


class DatasetReviewEvidenceReadRepository(Protocol):
    def get(self, evidence_id: str) -> DatasetReviewEvidence | None: ...

    def list_recent(self, limit: int = 20) -> tuple[DatasetReviewEvidence, ...]: ...


class LocalEvidenceFreshnessCoverageReadService:
    """Aggregate a bounded local evidence view without mutating any source record."""

    _MAX_RECORDS = 64

    def __init__(
        self,
        robustness: RobustnessEvidenceReadRepository,
        paper_runs: PaperRunEvidenceReadRepository,
        dataset_reviews: DatasetReviewEvidenceReadRepository,
    ) -> None:
        self._robustness = robustness
        self._paper_runs = paper_runs
        self._dataset_reviews = dataset_reviews
        self._linkage = LocalCrossEvidenceLinkageReadService(paper_runs, dataset_reviews)

    def read(
        self,
        *,
        policy: EvidenceFreshnessCoveragePolicy,
        evaluated_at: datetime | None = None,
    ) -> EvidenceFreshnessCoverageDashboard:
        moment = evaluated_at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("evidence coverage evaluation time must be timezone-aware")
        robustness_records = self._robustness.list_recent(self._MAX_RECORDS)
        paper_records = self._paper_runs.list_recent(self._MAX_RECORDS)
        review_records = self._dataset_reviews.list_recent(self._MAX_RECORDS)
        rows = tuple(self._row(paper, policy, moment) for paper in paper_records)
        return EvidenceFreshnessCoverageDashboard(
            policy_version=policy.policy_version,
            evaluated_at=moment,
            summary=EvidenceCoverageSummary(
                paper_total_count=len(paper_records),
                paper_current_count=sum(
                    self._freshness(item.evaluated_at, moment, policy) is EvidenceFreshness.CURRENT
                    for item in paper_records
                ),
                paper_stale_count=sum(
                    self._freshness(item.evaluated_at, moment, policy) is EvidenceFreshness.STALE
                    for item in paper_records
                ),
                paper_blocked_count=sum(item.state is PaperRunEligibilityState.BLOCKED for item in paper_records),
                robustness_total_count=len(robustness_records),
                robustness_current_count=sum(
                    self._freshness(item.created_at, moment, policy) is EvidenceFreshness.CURRENT
                    for item in robustness_records
                ),
                robustness_stale_count=sum(
                    self._freshness(item.created_at, moment, policy) is EvidenceFreshness.STALE
                    for item in robustness_records
                ),
                robustness_missing_count=sum(
                    row.robustness_freshness is EvidenceFreshness.UNKNOWN for row in rows
                ),
                review_total_count=len(review_records),
                review_current_count=sum(
                    self._freshness(item.evaluated_at, moment, policy) is EvidenceFreshness.CURRENT
                    for item in review_records
                ),
                review_stale_count=sum(
                    self._freshness(item.evaluated_at, moment, policy) is EvidenceFreshness.STALE
                    for item in review_records
                ),
                review_blocked_count=sum(item.state is DatasetReviewGateState.BLOCKED for item in review_records),
                review_missing_count=sum(
                    row.linkage_state == CrossEvidenceLinkageState.REVIEW_EVIDENCE_MISSING.value for row in rows
                ),
                exact_link_complete_count=sum(
                    row.linkage_state == CrossEvidenceLinkageState.LINKED_REVIEW_COMPLETE.value for row in rows
                ),
                exact_link_blocked_count=sum(
                    row.linkage_state == CrossEvidenceLinkageState.LINKED_REVIEW_BLOCKED.value for row in rows
                ),
                lineage_mismatch_count=sum(
                    row.linkage_state == CrossEvidenceLinkageState.LINEAGE_MISMATCH.value for row in rows
                ),
            ),
            rows=rows,
        )

    def _row(
        self,
        paper: PaperRunEligibilityEvidence,
        policy: EvidenceFreshnessCoveragePolicy,
        moment: datetime,
    ) -> EvidenceCoverageRow:
        conditions: list[str] = []
        paper_freshness = self._freshness(paper.evaluated_at, moment, policy)
        if paper_freshness is EvidenceFreshness.STALE:
            conditions.append("PAPER_RUN_EVIDENCE_STALE")
        elif paper_freshness is EvidenceFreshness.UNKNOWN:
            conditions.append("PAPER_RUN_EVIDENCE_TIME_AFTER_ASSESSMENT")
        if paper.state is PaperRunEligibilityState.BLOCKED:
            conditions.extend(f"PAPER_RUN_BLOCKED:{reason}" for reason in paper.blocking_reasons)

        robustness = self._robustness.get(paper.robustness_evidence_id) if paper.robustness_evidence_id else None
        if robustness is None:
            robustness_freshness = EvidenceFreshness.UNKNOWN
            conditions.append("ROBUSTNESS_EVIDENCE_MISSING")
        else:
            robustness_freshness = self._freshness(robustness.created_at, moment, policy)
            if robustness_freshness is EvidenceFreshness.STALE:
                conditions.append("ROBUSTNESS_EVIDENCE_STALE")
            elif robustness_freshness is EvidenceFreshness.UNKNOWN:
                conditions.append("ROBUSTNESS_EVIDENCE_TIME_AFTER_ASSESSMENT")

        linkage = self._linkage.link(paper.evidence_id)
        review = (
            self._dataset_reviews.get(linkage.dataset_review_evidence_id)
            if linkage.dataset_review_evidence_id is not None
            else None
        )
        if review is None:
            review_freshness = EvidenceFreshness.UNKNOWN
        else:
            review_freshness = self._freshness(review.evaluated_at, moment, policy)
            if review_freshness is EvidenceFreshness.STALE:
                conditions.append("DATASET_REVIEW_EVIDENCE_STALE")
            elif review_freshness is EvidenceFreshness.UNKNOWN:
                conditions.append("DATASET_REVIEW_EVIDENCE_TIME_AFTER_ASSESSMENT")
        conditions.extend(linkage.reasons)
        return EvidenceCoverageRow(
            paper_run_evidence_id=paper.evidence_id,
            batch_id=paper.batch_id,
            instrument_id=paper.instrument_id,
            dataset_id=paper.dataset_id,
            paper_state=paper.state.value,
            paper_freshness=paper_freshness,
            robustness_evidence_id=paper.robustness_evidence_id,
            robustness_freshness=robustness_freshness,
            dataset_review_evidence_id=linkage.dataset_review_evidence_id,
            dataset_review_freshness=review_freshness,
            linkage_state=linkage.state.value,
            conditions=tuple(dict.fromkeys(conditions)),
        )

    @staticmethod
    def _freshness(
        timestamp: datetime,
        moment: datetime,
        policy: EvidenceFreshnessCoveragePolicy,
    ) -> EvidenceFreshness:
        if timestamp > moment:
            return EvidenceFreshness.UNKNOWN
        if moment - timestamp > policy.maximum_evidence_age:
            return EvidenceFreshness.STALE
        return EvidenceFreshness.CURRENT
