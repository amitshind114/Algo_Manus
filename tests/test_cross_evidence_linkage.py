"""Option N acceptance tests for read-only paper-eligibility to dataset-review linkage."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.cross_evidence_linkage import (
    CrossEvidenceLinkageState,
    LocalCrossEvidenceLinkageReadService,
)
from algo_manus.application.dataset_review_gate import DatasetReviewEvidence, DatasetReviewGateState
from algo_manus.application.paper_run_eligibility import PaperRunEligibilityEvidence, PaperRunEligibilityState
from algo_manus.infrastructure.dataset_review.sqlite_repository import SqliteDatasetReviewEvidenceRepository
from algo_manus.infrastructure.paper_eligibility.sqlite_repository import SqlitePaperRunEligibilityEvidenceRepository


class CrossEvidenceLinkageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.moment = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)

    def _paper(self, *, evidence_id: str = "PEG-complete", dataset_id: str = "DATA-alpha", instrument_id: str = "FIXTURE:ALPHA") -> PaperRunEligibilityEvidence:
        return PaperRunEligibilityEvidence(
            evidence_id=evidence_id,
            state=PaperRunEligibilityState.EVIDENCE_COMPLETE,
            batch_id="EXP-alpha",
            instrument_id=instrument_id,
            manifest_id="RUN-alpha",
            dataset_id=dataset_id,
            strategy_id="sma_crossover",
            strategy_version="1.0.0",
            parameter_revision_id="PARAM-alpha",
            robustness_evidence_id="ROB-alpha",
            policy_version="paper-evidence-v1",
            central_policy_version="central-risk-v1",
            kill_switch_change_id="KILL-alpha",
            blocking_reasons=(),
            evaluated_at=self.moment,
        )

    def _review(
        self,
        *,
        evidence_id: str = "DREV-complete",
        state: DatasetReviewGateState = DatasetReviewGateState.REVIEW_COMPLETE,
        dataset_id: str = "DATA-alpha",
        instrument_id: str = "FIXTURE:ALPHA",
        reasons: tuple[str, ...] = (),
    ) -> DatasetReviewEvidence:
        return DatasetReviewEvidence(
            evidence_id=evidence_id,
            state=state,
            dataset_id=dataset_id,
            instrument_id=instrument_id,
            interval="1d",
            provenance_raw_content_sha256="a" * 64,
            adjustment_basis="declared retained basis",
            corporate_action_review=None,
            calendar_review=None,
            policy_version="dataset-review-v1",
            blocking_reasons=reasons,
            evaluated_at=self.moment,
        )

    def test_matching_complete_review_links_restart_safely_and_is_non_actionable(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            papers = SqlitePaperRunEligibilityEvidenceRepository(root / "paper.sqlite3")
            reviews = SqliteDatasetReviewEvidenceRepository(root / "review.sqlite3")
            paper = self._paper()
            review = self._review()
            papers.save(paper)
            reviews.save(review)
            linked = LocalCrossEvidenceLinkageReadService(papers, reviews).link(paper.evidence_id)
            restarted = LocalCrossEvidenceLinkageReadService(
                SqlitePaperRunEligibilityEvidenceRepository(root / "paper.sqlite3"),
                SqliteDatasetReviewEvidenceRepository(root / "review.sqlite3"),
            ).link(paper.evidence_id)

        self.assertEqual(linked.state, CrossEvidenceLinkageState.LINKED_REVIEW_COMPLETE)
        self.assertEqual(linked.dataset_review_evidence_id, review.evidence_id)
        self.assertEqual(linked.reasons, ())
        self.assertEqual(restarted, linked)
        self.assertFalse(hasattr(linked, "approve"))
        self.assertFalse(hasattr(LocalCrossEvidenceLinkageReadService, "submit"))

    def test_missing_blocked_and_mismatched_review_evidence_are_named_without_fallback(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            papers = SqlitePaperRunEligibilityEvidenceRepository(root / "paper.sqlite3")
            reviews = SqliteDatasetReviewEvidenceRepository(root / "review.sqlite3")
            paper = self._paper()
            papers.save(paper)
            service = LocalCrossEvidenceLinkageReadService(papers, reviews)
            missing = service.link(paper.evidence_id)
            blocked = self._review(
                state=DatasetReviewGateState.BLOCKED,
                reasons=("CORPORATE_ACTION_REVIEW_MISSING",),
            )
            reviews.save(blocked)
            blocked_link = service.link(paper.evidence_id)
            mismatch_paper = self._paper(
                evidence_id="PEG-mismatch",
                dataset_id="DATA-target",
                instrument_id="FIXTURE:TARGET",
            )
            papers.save(mismatch_paper)
            reviews.save(
                self._review(
                    evidence_id="DREV-dataset-mismatch",
                    dataset_id="DATA-other",
                    instrument_id="FIXTURE:TARGET",
                )
            )
            reviews.save(
                self._review(
                    evidence_id="DREV-instrument-mismatch",
                    dataset_id="DATA-target",
                    instrument_id="FIXTURE:OTHER",
                )
            )
            mismatched = service.link(mismatch_paper.evidence_id)

        self.assertEqual(missing.state, CrossEvidenceLinkageState.REVIEW_EVIDENCE_MISSING)
        self.assertIn("DATASET_REVIEW_EVIDENCE_MISSING", missing.reasons)
        self.assertEqual(blocked_link.state, CrossEvidenceLinkageState.LINKED_REVIEW_BLOCKED)
        self.assertIn("DATASET_REVIEW_BLOCKED:CORPORATE_ACTION_REVIEW_MISSING", blocked_link.reasons)
        self.assertEqual(mismatched.state, CrossEvidenceLinkageState.LINEAGE_MISMATCH)
        self.assertIn("DATASET_REVIEW_DATASET_MISMATCH", mismatched.reasons)
        self.assertIn("DATASET_REVIEW_INSTRUMENT_MISMATCH", mismatched.reasons)


if __name__ == "__main__":
    unittest.main()
