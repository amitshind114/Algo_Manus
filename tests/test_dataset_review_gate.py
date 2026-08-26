"""Option M acceptance tests for local corporate-action and calendar review evidence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.dataset_review_gate import (
    DatasetReviewDeclaration,
    DatasetReviewDisposition,
    DatasetReviewGateState,
    LocalDatasetReviewGateService,
    LocalDatasetReviewPolicy,
)
from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.infrastructure.dataset_review.sqlite_repository import SqliteDatasetReviewEvidenceRepository


class DatasetReviewGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
        self.policy = LocalDatasetReviewPolicy("dataset-review-v1", max_review_age=timedelta(days=90))
        self.dataset = self._dataset()

    def _dataset(self) -> CandleDataset:
        start = datetime(2026, 7, 1, 9, 15, tzinfo=timezone.utc)
        return CandleDataset.create(
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            interval="1d",
            provenance=DataProvenance(
                source_name="option-m-fixture",
                source_kind=DataSourceKind.FIXTURE,
                source_uri="fixture://option-m/alpha-v1",
                retrieved_at=start,
                raw_content_sha256=sha256(b"option-m-fixture-alpha-v1").hexdigest(),
                adjustment_basis="synthetic fixture bars; no market-data adjustment claim",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=tuple(
                Candle(
                    timestamp=start + timedelta(days=index),
                    open=100 + index,
                    high=101 + index,
                    low=99 + index,
                    close=100 + index,
                    volume=1_000,
                )
                for index in range(10)
            ),
        )

    def _review(self, *, disposition: DatasetReviewDisposition = DatasetReviewDisposition.REVIEWED, reviewed_at: datetime | None = None, scope_start: datetime | None = None) -> DatasetReviewDeclaration:
        return DatasetReviewDeclaration(
            disposition=disposition,
            scope_start=scope_start or self.dataset.candles[0].timestamp,
            scope_end=self.dataset.candles[-1].timestamp,
            source_reference="local://review-register/option-m-v1",
            reviewed_at=reviewed_at or self.now,
            note="local declared review evidence; no external data retrieval occurred",
        )

    def test_complete_declared_reviews_are_immutable_restart_safe_and_non_actionable(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "dataset_review.sqlite3"
            evidence = LocalDatasetReviewGateService(SqliteDatasetReviewEvidenceRepository(path)).evaluate(
                dataset=self.dataset,
                corporate_action_review=self._review(),
                calendar_review=self._review(),
                policy=self.policy,
                evaluated_at=self.now,
            )
            replayed = LocalDatasetReviewGateService(SqliteDatasetReviewEvidenceRepository(path)).evaluate(
                dataset=self.dataset,
                corporate_action_review=self._review(),
                calendar_review=self._review(),
                policy=self.policy,
                evaluated_at=self.now,
            )

        self.assertEqual(evidence.state, DatasetReviewGateState.REVIEW_COMPLETE)
        self.assertEqual(evidence.blocking_reasons, ())
        self.assertEqual(replayed, evidence)
        self.assertTrue(evidence.evidence_id.startswith("DREV-"))
        self.assertFalse(hasattr(evidence, "approve"))
        self.assertFalse(hasattr(LocalDatasetReviewGateService, "submit"))

    def test_missing_unresolved_stale_and_scope_incomplete_reviews_are_explicitly_blocked(self) -> None:
        with TemporaryDirectory() as directory:
            service = LocalDatasetReviewGateService(
                SqliteDatasetReviewEvidenceRepository(Path(directory) / "dataset_review.sqlite3")
            )
            missing = service.evaluate(
                dataset=self.dataset,
                corporate_action_review=None,
                calendar_review=None,
                policy=self.policy,
                evaluated_at=self.now,
            )
            unresolved = service.evaluate(
                dataset=self.dataset,
                corporate_action_review=self._review(disposition=DatasetReviewDisposition.UNRESOLVED),
                calendar_review=self._review(),
                policy=self.policy,
                evaluated_at=self.now,
            )
            stale = service.evaluate(
                dataset=self.dataset,
                corporate_action_review=self._review(reviewed_at=self.now - timedelta(days=91)),
                calendar_review=self._review(reviewed_at=self.now - timedelta(days=91)),
                policy=self.policy,
                evaluated_at=self.now,
            )
            incomplete_scope = service.evaluate(
                dataset=self.dataset,
                corporate_action_review=self._review(scope_start=self.dataset.candles[1].timestamp),
                calendar_review=self._review(),
                policy=self.policy,
                evaluated_at=self.now,
            )

        self.assertEqual(missing.state, DatasetReviewGateState.BLOCKED)
        self.assertIn("CORPORATE_ACTION_REVIEW_MISSING", missing.blocking_reasons)
        self.assertIn("CALENDAR_REVIEW_MISSING", missing.blocking_reasons)
        self.assertIn("CORPORATE_ACTION_REVIEW_UNRESOLVED", unresolved.blocking_reasons)
        self.assertIn("CORPORATE_ACTION_REVIEW_STALE", stale.blocking_reasons)
        self.assertIn("CALENDAR_REVIEW_STALE", stale.blocking_reasons)
        self.assertIn("CORPORATE_ACTION_REVIEW_SCOPE_INCOMPLETE", incomplete_scope.blocking_reasons)


if __name__ == "__main__":
    unittest.main()
