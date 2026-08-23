from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.application.dataset_validation import (
    ResearchDatasetValidationError,
    ResearchDatasetValidator,
)
from algo_manus.application.experiments import BatchBacktestRequest, ExperimentBatchService
from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.domain.research import DataValidationStatus
from algo_manus.domain.strategy import StrategyParameterRevision
from algo_manus.infrastructure.experiments.sqlite_repository import SqliteExperimentBatchRepository
from algo_manus.infrastructure.research import SqliteResearchEvidenceRepository
from algo_manus.strategies import SmaCrossoverStrategy


class ResearchDatasetValidatorTests(unittest.TestCase):
    def _dataset(
        self,
        *,
        candles: int = 4,
        step_days: int = 1,
        use_case: DataUseCase = DataUseCase.RESEARCH,
        source_kind: DataSourceKind = DataSourceKind.FIXTURE,
    ) -> CandleDataset:
        start = datetime(2026, 8, 1, 9, 15, tzinfo=timezone.utc)
        return CandleDataset.create(
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            interval="1d",
            provenance=DataProvenance(
                source_name="fixture-validation",
                source_kind=source_kind,
                source_uri="fixture://validation/dataset",
                retrieved_at=start,
                raw_content_sha256=sha256(f"{candles}-{step_days}-{use_case}-{source_kind}".encode()).hexdigest(),
                adjustment_basis="synthetic unadjusted bars",
                use_case=use_case,
            ),
            candles=tuple(
                Candle(
                    timestamp=start + timedelta(days=index * step_days),
                    open=100 + index,
                    high=101 + index,
                    low=99 + index,
                    close=100 + index,
                    volume=1_000,
                )
                for index in range(candles)
            ),
        )

    def test_qualifying_fixture_dataset_is_accepted(self) -> None:
        outcome = ResearchDatasetValidator().validate(
            self._dataset(), validated_at=datetime(2026, 8, 2, 9, 15, tzinfo=timezone.utc)
        )

        self.assertEqual(outcome.status, DataValidationStatus.ACCEPTED)
        self.assertFalse(outcome.issues)

    def test_history_and_use_case_are_rejected_while_excessive_gap_is_quarantined(self) -> None:
        validator = ResearchDatasetValidator()
        insufficient = validator.validate(
            self._dataset(candles=2), validated_at=datetime(2026, 8, 2, 9, 15, tzinfo=timezone.utc)
        )
        paper = validator.validate(
            self._dataset(use_case=DataUseCase.PAPER), validated_at=datetime(2026, 8, 2, 9, 15, tzinfo=timezone.utc)
        )
        gappy = validator.validate(
            self._dataset(step_days=4), validated_at=datetime(2026, 8, 2, 9, 15, tzinfo=timezone.utc)
        )

        self.assertEqual(insufficient.status, DataValidationStatus.REJECTED)
        self.assertIn("INSUFFICIENT_HISTORY", {item.code for item in insufficient.issues})
        self.assertEqual(paper.status, DataValidationStatus.REJECTED)
        self.assertIn("USE_CASE_NOT_RESEARCH", {item.code for item in paper.issues})
        self.assertEqual(gappy.status, DataValidationStatus.QUARANTINED)
        self.assertIn("GAP_EXCEEDS_POLICY", {item.code for item in gappy.issues})

    def test_experiment_blocks_quarantined_dataset_before_backtesting(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory)
            dataset = self._dataset(candles=6, step_days=4)
            service = ExperimentBatchService(
                BarBacktestService(),
                SqliteExperimentBatchRepository(path / "experiments.sqlite3"),
                SqliteResearchEvidenceRepository(path / "research.sqlite3"),
            )

            with self.assertRaisesRegex(ResearchDatasetValidationError, "QUARANTINED"):
                service.run(
                    request=BatchBacktestRequest(
                        universe_id="fixture-universe",
                        universe_snapshot_id="FIXTURE-SNAPSHOT-LOCAL-V1",
                        datasets_by_instrument={dataset.instrument_id: dataset},
                        initial_cash=1_000,
                        quantity=10,
                        commission_bps=0,
                        slippage_bps=0,
                    ),
                    strategy=SmaCrossoverStrategy(),
                    parameters=StrategyParameterRevision.create(
                        "sma_crossover", {"fast_window": 2, "slow_window": 3}
                    ),
                    created_at=datetime(2026, 8, 2, 9, 15, tzinfo=timezone.utc),
                )


if __name__ == "__main__":
    unittest.main()
