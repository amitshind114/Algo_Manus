"""Option O acceptance tests for read-only evidence freshness and lineage coverage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.evidence_coverage_dashboard import (
    EvidenceFreshness,
    EvidenceFreshnessCoveragePolicy,
    LocalEvidenceFreshnessCoverageReadService,
)
from algo_manus.application.dataset_review_gate import DatasetReviewEvidence, DatasetReviewGateState
from algo_manus.application.paper_run_eligibility import PaperRunEligibilityEvidence, PaperRunEligibilityState
from algo_manus.application.robustness import RobustnessEvidence, RobustnessGateState, RobustnessSplitPolicy
from algo_manus.infrastructure.dataset_review.sqlite_repository import SqliteDatasetReviewEvidenceRepository
from algo_manus.infrastructure.paper_eligibility.sqlite_repository import SqlitePaperRunEligibilityEvidenceRepository
from algo_manus.infrastructure.robustness.sqlite_repository import SqliteRobustnessEvidenceRepository


class EvidenceCoverageDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
        self.policy = EvidenceFreshnessCoveragePolicy("coverage-v1", maximum_evidence_age=timedelta(days=30))

    def _robustness(self, *, evidence_id: str, dataset_id: str, created_at: datetime) -> RobustnessEvidence:
        return RobustnessEvidence(
            evidence_id=evidence_id,
            dataset_id=dataset_id,
            strategy_id="sma_crossover",
            strategy_version="1.0.0",
            split_policy=RobustnessSplitPolicy(in_sample_ratio=0.5, max_grid_cells=4),
            in_sample_end=datetime(2026, 7, 7, 9, 15, tzinfo=timezone.utc),
            holdout_start=datetime(2026, 7, 9, 9, 15, tzinfo=timezone.utc),
            gate_state=RobustnessGateState.INFORMATIONAL_ONLY,
            candidates=(),
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
            force_close_at_end=True,
            selection_bias_warning="bounded fixture warning",
            created_at=created_at,
        )

    def _paper(
        self,
        *,
        evidence_id: str,
        dataset_id: str,
        instrument_id: str,
        robustness_evidence_id: str | None,
        evaluated_at: datetime,
        state: PaperRunEligibilityState = PaperRunEligibilityState.EVIDENCE_COMPLETE,
    ) -> PaperRunEligibilityEvidence:
        return PaperRunEligibilityEvidence(
            evidence_id=evidence_id,
            state=state,
            batch_id=f"EXP-{evidence_id}",
            instrument_id=instrument_id,
            manifest_id=f"RUN-{evidence_id}",
            dataset_id=dataset_id,
            strategy_id="sma_crossover",
            strategy_version="1.0.0",
            parameter_revision_id="PARAM-v1",
            robustness_evidence_id=robustness_evidence_id,
            policy_version="paper-evidence-v1",
            central_policy_version="central-risk-v1",
            kill_switch_change_id="KILL-v1",
            blocking_reasons=("ROBUSTNESS_HISTORY_INSUFFICIENT",) if state is PaperRunEligibilityState.BLOCKED else (),
            evaluated_at=evaluated_at,
        )

    def _review(
        self,
        *,
        evidence_id: str,
        dataset_id: str,
        instrument_id: str,
        evaluated_at: datetime,
        state: DatasetReviewGateState = DatasetReviewGateState.REVIEW_COMPLETE,
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
            blocking_reasons=("CALENDAR_REVIEW_MISSING",) if state is DatasetReviewGateState.BLOCKED else (),
            evaluated_at=evaluated_at,
        )

    def test_current_exact_lineage_coverage_survives_restart_without_writing(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            robustness = SqliteRobustnessEvidenceRepository(root / "robustness.sqlite3")
            papers = SqlitePaperRunEligibilityEvidenceRepository(root / "paper.sqlite3")
            reviews = SqliteDatasetReviewEvidenceRepository(root / "review.sqlite3")
            robustness.save(self._robustness(evidence_id="ROB-current", dataset_id="DATA-alpha", created_at=self.now))
            paper = self._paper(
                evidence_id="PEG-current",
                dataset_id="DATA-alpha",
                instrument_id="FIXTURE:ALPHA",
                robustness_evidence_id="ROB-current",
                evaluated_at=self.now,
            )
            papers.save(paper)
            reviews.save(
                self._review(
                    evidence_id="DREV-current",
                    dataset_id="DATA-alpha",
                    instrument_id="FIXTURE:ALPHA",
                    evaluated_at=self.now,
                )
            )
            dashboard = LocalEvidenceFreshnessCoverageReadService(robustness, papers, reviews).read(
                policy=self.policy,
                evaluated_at=self.now,
            )
            restarted = LocalEvidenceFreshnessCoverageReadService(
                SqliteRobustnessEvidenceRepository(root / "robustness.sqlite3"),
                SqlitePaperRunEligibilityEvidenceRepository(root / "paper.sqlite3"),
                SqliteDatasetReviewEvidenceRepository(root / "review.sqlite3"),
            ).read(policy=self.policy, evaluated_at=self.now)

        self.assertEqual(dashboard, restarted)
        self.assertEqual(dashboard.summary.paper_current_count, 1)
        self.assertEqual(dashboard.summary.robustness_current_count, 1)
        self.assertEqual(dashboard.summary.review_current_count, 1)
        self.assertEqual(dashboard.summary.exact_link_complete_count, 1)
        self.assertEqual(dashboard.rows[0].paper_freshness, EvidenceFreshness.CURRENT)
        self.assertFalse(hasattr(LocalEvidenceFreshnessCoverageReadService, "refresh"))

    def test_stale_missing_blocked_and_mismatched_lineage_are_counted_without_fallback(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            robustness = SqliteRobustnessEvidenceRepository(root / "robustness.sqlite3")
            papers = SqlitePaperRunEligibilityEvidenceRepository(root / "paper.sqlite3")
            reviews = SqliteDatasetReviewEvidenceRepository(root / "review.sqlite3")
            old = self.now - timedelta(days=31)
            robustness.save(self._robustness(evidence_id="ROB-stale", dataset_id="DATA-stale", created_at=old))
            papers.save(
                self._paper(
                    evidence_id="PEG-missing-review",
                    dataset_id="DATA-stale",
                    instrument_id="FIXTURE:STALE",
                    robustness_evidence_id="ROB-stale",
                    evaluated_at=old,
                    state=PaperRunEligibilityState.BLOCKED,
                )
            )
            papers.save(
                self._paper(
                    evidence_id="PEG-mismatch",
                    dataset_id="DATA-target",
                    instrument_id="FIXTURE:TARGET",
                    robustness_evidence_id="ROB-absent",
                    evaluated_at=self.now,
                )
            )
            reviews.save(
                self._review(
                    evidence_id="DREV-dataset-mismatch",
                    dataset_id="DATA-other",
                    instrument_id="FIXTURE:TARGET",
                    evaluated_at=self.now,
                    state=DatasetReviewGateState.BLOCKED,
                )
            )
            reviews.save(
                self._review(
                    evidence_id="DREV-instrument-mismatch",
                    dataset_id="DATA-target",
                    instrument_id="FIXTURE:OTHER",
                    evaluated_at=self.now,
                )
            )
            dashboard = LocalEvidenceFreshnessCoverageReadService(robustness, papers, reviews).read(
                policy=self.policy,
                evaluated_at=self.now,
            )

        self.assertEqual(dashboard.summary.paper_stale_count, 1)
        self.assertEqual(dashboard.summary.robustness_stale_count, 1)
        self.assertEqual(dashboard.summary.paper_blocked_count, 1)
        self.assertEqual(dashboard.summary.review_missing_count, 1)
        self.assertEqual(dashboard.summary.lineage_mismatch_count, 1)
        mismatch = next(item for item in dashboard.rows if item.paper_run_evidence_id == "PEG-mismatch")
        self.assertEqual(mismatch.robustness_freshness, EvidenceFreshness.UNKNOWN)
        self.assertIn("ROBUSTNESS_EVIDENCE_MISSING", mismatch.conditions)
        self.assertIn("DATASET_REVIEW_DATASET_MISMATCH", mismatch.conditions)
        self.assertIn("DATASET_REVIEW_INSTRUMENT_MISMATCH", mismatch.conditions)


if __name__ == "__main__":
    unittest.main()
