"""Read-only linkage between retained paper-run and dataset-review evidence.

The linkage is a view over two immutable local evidence stores. It never writes
either store and cannot modify promotion, risk, paper, broker, or execution state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from algo_manus.application.dataset_review_gate import (
    DatasetReviewEvidence,
    DatasetReviewGateState,
)
from algo_manus.application.paper_run_eligibility import PaperRunEligibilityEvidence


class CrossEvidenceLinkageState(StrEnum):
    """Informational cross-evidence relationship; no state grants authority."""

    LINKED_REVIEW_COMPLETE = "LINKED_REVIEW_COMPLETE"
    LINKED_REVIEW_BLOCKED = "LINKED_REVIEW_BLOCKED"
    REVIEW_EVIDENCE_MISSING = "REVIEW_EVIDENCE_MISSING"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    PAPER_EVIDENCE_MISSING = "PAPER_EVIDENCE_MISSING"


@dataclass(frozen=True, slots=True)
class CrossEvidenceLinkage:
    """A read-only explanation of one paper-evidence record's dataset-review link."""

    paper_run_evidence_id: str
    state: CrossEvidenceLinkageState
    batch_id: str | None
    paper_instrument_id: str | None
    paper_dataset_id: str | None
    paper_run_state: str | None
    dataset_review_evidence_id: str | None
    dataset_review_state: str | None
    review_instrument_id: str | None
    review_dataset_id: str | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.paper_run_evidence_id.strip():
            raise ValueError("paper-run evidence ID is required for cross-evidence linkage")
        if self.state is CrossEvidenceLinkageState.LINKED_REVIEW_COMPLETE and self.reasons:
            raise ValueError("complete linkage cannot contain reasons")
        if self.state is not CrossEvidenceLinkageState.LINKED_REVIEW_COMPLETE and not self.reasons:
            raise ValueError("non-complete linkage requires named reasons")


class PaperRunEligibilityReadRepository(Protocol):
    def get(self, evidence_id: str) -> PaperRunEligibilityEvidence | None: ...


class DatasetReviewReadRepository(Protocol):
    def list_recent(self, limit: int = 20) -> tuple[DatasetReviewEvidence, ...]: ...


class LocalCrossEvidenceLinkageReadService:
    """Read retained cross-evidence lineage without selecting, promoting, or mutating evidence."""

    def __init__(
        self,
        paper_evidence: PaperRunEligibilityReadRepository,
        dataset_reviews: DatasetReviewReadRepository,
    ) -> None:
        self._paper_evidence = paper_evidence
        self._dataset_reviews = dataset_reviews

    def link(self, paper_run_evidence_id: str) -> CrossEvidenceLinkage:
        if not paper_run_evidence_id.strip():
            raise ValueError("paper-run evidence ID is required")
        paper = self._paper_evidence.get(paper_run_evidence_id)
        if paper is None:
            return CrossEvidenceLinkage(
                paper_run_evidence_id=paper_run_evidence_id,
                state=CrossEvidenceLinkageState.PAPER_EVIDENCE_MISSING,
                batch_id=None,
                paper_instrument_id=None,
                paper_dataset_id=None,
                paper_run_state=None,
                dataset_review_evidence_id=None,
                dataset_review_state=None,
                review_instrument_id=None,
                review_dataset_id=None,
                reasons=("PAPER_RUN_EVIDENCE_MISSING",),
            )

        if paper.dataset_id is None:
            return self._unlinked(paper, "PAPER_RUN_DATASET_LINEAGE_MISSING")
        reviews = self._dataset_reviews.list_recent(limit=64)
        exact = tuple(
            item
            for item in reviews
            if item.dataset_id == paper.dataset_id and item.instrument_id == paper.instrument_id
        )
        if exact:
            # Repository ordering is retained assessment-time ordering; no performance,
            # strategy, promotion, or risk outcome is used to choose this displayed row.
            review = exact[0]
            if review.state is DatasetReviewGateState.REVIEW_COMPLETE:
                return CrossEvidenceLinkage(
                    paper_run_evidence_id=paper.evidence_id,
                    state=CrossEvidenceLinkageState.LINKED_REVIEW_COMPLETE,
                    batch_id=paper.batch_id,
                    paper_instrument_id=paper.instrument_id,
                    paper_dataset_id=paper.dataset_id,
                    paper_run_state=paper.state.value,
                    dataset_review_evidence_id=review.evidence_id,
                    dataset_review_state=review.state.value,
                    review_instrument_id=review.instrument_id,
                    review_dataset_id=review.dataset_id,
                    reasons=(),
                )
            return CrossEvidenceLinkage(
                paper_run_evidence_id=paper.evidence_id,
                state=CrossEvidenceLinkageState.LINKED_REVIEW_BLOCKED,
                batch_id=paper.batch_id,
                paper_instrument_id=paper.instrument_id,
                paper_dataset_id=paper.dataset_id,
                paper_run_state=paper.state.value,
                dataset_review_evidence_id=review.evidence_id,
                dataset_review_state=review.state.value,
                review_instrument_id=review.instrument_id,
                review_dataset_id=review.dataset_id,
                reasons=tuple(f"DATASET_REVIEW_BLOCKED:{reason}" for reason in review.blocking_reasons),
            )

        reasons: list[str] = []
        if any(item.instrument_id == paper.instrument_id for item in reviews):
            reasons.append("DATASET_REVIEW_DATASET_MISMATCH")
        if any(item.dataset_id == paper.dataset_id for item in reviews):
            reasons.append("DATASET_REVIEW_INSTRUMENT_MISMATCH")
        if not reasons:
            return self._unlinked(paper, "DATASET_REVIEW_EVIDENCE_MISSING")
        return CrossEvidenceLinkage(
            paper_run_evidence_id=paper.evidence_id,
            state=CrossEvidenceLinkageState.LINEAGE_MISMATCH,
            batch_id=paper.batch_id,
            paper_instrument_id=paper.instrument_id,
            paper_dataset_id=paper.dataset_id,
            paper_run_state=paper.state.value,
            dataset_review_evidence_id=None,
            dataset_review_state=None,
            review_instrument_id=None,
            review_dataset_id=None,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _unlinked(paper: PaperRunEligibilityEvidence, reason: str) -> CrossEvidenceLinkage:
        return CrossEvidenceLinkage(
            paper_run_evidence_id=paper.evidence_id,
            state=CrossEvidenceLinkageState.REVIEW_EVIDENCE_MISSING,
            batch_id=paper.batch_id,
            paper_instrument_id=paper.instrument_id,
            paper_dataset_id=paper.dataset_id,
            paper_run_state=paper.state.value,
            dataset_review_evidence_id=None,
            dataset_review_state=None,
            review_instrument_id=None,
            review_dataset_id=None,
            reasons=(reason,),
        )
