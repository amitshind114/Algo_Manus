from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.domain.research import (
    DataValidationIssue,
    DataValidationSeverity,
    DataValidationStatus,
    DatasetLineage,
    DatasetValidationOutcome,
    ResearchExecutionAssumptions,
    ResearchRunManifest,
)


class ResearchManifestTests(unittest.TestCase):
    def _dataset(self, use_case: DataUseCase = DataUseCase.RESEARCH) -> CandleDataset:
        start = datetime(2026, 8, 1, 9, 15, tzinfo=timezone.utc)
        return CandleDataset.create(
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            interval="1d",
            provenance=DataProvenance(
                source_name="fixture-research",
                source_kind=DataSourceKind.FIXTURE,
                source_uri="fixture://research/alpha",
                retrieved_at=start,
                raw_content_sha256=sha256(b"research-manifest-fixture").hexdigest(),
                adjustment_basis="synthetic unadjusted bars",
                use_case=use_case,
            ),
            candles=(
                Candle(timestamp=start, open=100, high=101, low=99, close=100, volume=1_000),
                Candle(timestamp=start + timedelta(days=1), open=101, high=102, low=100, close=101, volume=1_100),
            ),
        )

    def _manifest(self, *, created_at: datetime | None = None, outcome: DatasetValidationOutcome | None = None, use_case: DataUseCase = DataUseCase.RESEARCH) -> ResearchRunManifest:
        dataset = self._dataset(use_case)
        lineage = DatasetLineage.from_dataset(dataset)
        start = dataset.candles[0].timestamp
        accepted = outcome or DatasetValidationOutcome(
            dataset_id=dataset.dataset_id,
            status=DataValidationStatus.ACCEPTED,
            policy_version="dataset-validation-v1",
            validated_at=start + timedelta(hours=1),
        )
        return ResearchRunManifest(
            universe_id="fixture-nse-equity-universe",
            universe_snapshot_id="FIXTURE-SNAPSHOT-LOCAL-V1",
            strategy_id="sma_crossover",
            strategy_version="1.0.0",
            parameter_revision_id="PARAM-test",
            engine_version="backtest-v1",
            lineages=(lineage,),
            validation_outcomes=(accepted,),
            execution_assumptions=ResearchExecutionAssumptions(
                initial_cash=100_000,
                quantity=100,
                commission_bps=10,
                slippage_bps=5,
            ),
            start=start,
            end=start + timedelta(days=1),
            information_cutoff=start,
            created_at=created_at or start + timedelta(hours=2),
            git_commit_sha="fb5b964",
        )

    def test_manifest_identity_is_deterministic_across_creation_timestamps(self) -> None:
        first = self._manifest(created_at=datetime(2026, 8, 1, 11, 15, tzinfo=timezone.utc))
        second = self._manifest(created_at=datetime(2026, 8, 2, 11, 15, tzinfo=timezone.utc))

        self.assertEqual(first.manifest_id, second.manifest_id)
        self.assertTrue(first.manifest_id.startswith("RUN-"))
        self.assertEqual(first.lineages[0].raw_content_sha256, self._dataset().provenance.raw_content_sha256)

    def test_manifest_rejects_non_research_or_non_accepted_data(self) -> None:
        rejected_dataset = self._dataset()
        rejected = DatasetValidationOutcome(
            dataset_id=rejected_dataset.dataset_id,
            status=DataValidationStatus.REJECTED,
            policy_version="dataset-validation-v1",
            validated_at=datetime(2026, 8, 1, 10, 15, tzinfo=timezone.utc),
            issues=(
                DataValidationIssue(
                    code="DUPLICATE_TIMESTAMP",
                    severity=DataValidationSeverity.ERROR,
                    message="duplicate candle timestamp detected",
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "quarantined or rejected"):
            self._manifest(outcome=rejected)
        with self.assertRaisesRegex(ValueError, "research-use"):
            self._manifest(use_case=DataUseCase.PAPER)

    def test_validation_outcome_rejects_silent_error_acceptance(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot contain error"):
            DatasetValidationOutcome(
                dataset_id="DATA-123",
                status=DataValidationStatus.ACCEPTED,
                policy_version="dataset-validation-v1",
                validated_at=datetime(2026, 8, 1, 10, 15, tzinfo=timezone.utc),
                issues=(
                    DataValidationIssue(
                        code="GAP",
                        severity=DataValidationSeverity.ERROR,
                        message="unexplained data gap",
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
