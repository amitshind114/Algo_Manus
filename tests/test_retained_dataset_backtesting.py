from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from algo_manus.application.dataset_validation import ResearchDatasetValidationError
from algo_manus.application.retained_dataset_backtesting import (
    RetainedDatasetBacktestRequest,
    RetainedDatasetBacktestService,
)
from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.infrastructure.experiments.sqlite_repository import SqliteExperimentBatchRepository
from algo_manus.infrastructure.research import SqliteResearchEvidenceRepository


class MemoryCandleRepository:
    def __init__(self, datasets: tuple[CandleDataset, ...]) -> None:
        self._datasets = {item.dataset_id: item for item in datasets}

    def get(self, dataset_id: str) -> CandleDataset | None:
        return self._datasets.get(dataset_id)

    def list_recent(self, *, source_name: str, limit: int = 20) -> tuple[CandleDataset, ...]:
        return tuple(
            item
            for item in self._datasets.values()
            if item.provenance.source_name == source_name
        )[:limit]


class RetainedDatasetBacktestServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.start = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)
        self.dataset = self._dataset()
        self.batches = SqliteExperimentBatchRepository(Path(self.temp_dir.name) / "experiments.sqlite3")
        self.manifests = SqliteResearchEvidenceRepository(Path(self.temp_dir.name) / "research.sqlite3")
        self.service = RetainedDatasetBacktestService(
            MemoryCandleRepository((self.dataset,)),
            self.batches,
            self.manifests,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _dataset(self, *, source_kind: DataSourceKind = DataSourceKind.BROKER, gap: bool = False) -> CandleDataset:
        instrument_id = "ANGEL_ONE:NSE:NSE:500325"
        candles = tuple(
            Candle(
                timestamp=self.start + timedelta(days=index + (4 if gap and index >= 4 else 0)),
                open=close - 0.2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=1000,
            )
            for index, close in enumerate([10, 9, 8, 9, 11, 14, 13, 10, 8])
        )
        return CandleDataset.create(
            instrument_id=instrument_id,
            interval="1d",
            provenance=DataProvenance(
                source_name="angel_one",
                source_kind=source_kind,
                source_uri="https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleData",
                retrieved_at=self.start + timedelta(days=20),
                raw_content_sha256=sha256(f"{source_kind.value}:{gap}".encode()).hexdigest(),
                adjustment_basis="unadjusted broker historical candles",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=candles,
        )

    def _request(self, dataset_id: str | None = None) -> RetainedDatasetBacktestRequest:
        return RetainedDatasetBacktestRequest(
            dataset_id=dataset_id or self.dataset.dataset_id,
            strategy_id="sma_crossover",
            parameters={"fast_window": 2, "slow_window": 3},
            initial_cash=1_000,
            quantity=10,
            commission_bps=0,
            slippage_bps=0,
        )

    def test_runs_only_the_explicit_retained_broker_dataset_and_pins_full_lineage(self) -> None:
        created_at = datetime(2026, 8, 25, 10, tzinfo=timezone.utc)
        run = self.service.run(self._request(), now=created_at)
        stored = self.batches.get(run.batch.batch_id)
        manifest = self.manifests.get(run.batch.research_manifest_id or "")

        self.assertEqual(run.dataset.dataset_id, self.dataset.dataset_id)
        self.assertEqual(run.validation.dataset_id, self.dataset.dataset_id)
        self.assertTrue(run.validation.research_eligible)
        self.assertIsNotNone(stored)
        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest.lineages[0].dataset_id, self.dataset.dataset_id)
        self.assertEqual(manifest.lineages[0].raw_content_sha256, self.dataset.provenance.raw_content_sha256)
        self.assertEqual(manifest.information_cutoff, self.dataset.candles[-1].timestamp)
        self.assertEqual(run.batch.universe_snapshot_id, f"DATASET:{self.dataset.dataset_id}")
        result = run.batch.results[0].backtest
        self.assertTrue(all(trade.entry_time > self.dataset.candles[2].timestamp for trade in result.trades))

    def test_missing_dataset_or_non_broker_dataset_fails_without_silent_fallback(self) -> None:
        with self.assertRaisesRegex(LookupError, "retained historical dataset"):
            self.service.run(self._request("DATASET-missing"), now=self.start)

        fixture = self._dataset(source_kind=DataSourceKind.FIXTURE)
        fixture_service = RetainedDatasetBacktestService(
            MemoryCandleRepository((fixture,)), self.batches, self.manifests
        )
        with self.assertRaisesRegex(ValueError, "broker historical"):
            fixture_service.run(self._request(fixture.dataset_id), now=self.start)
        self.assertEqual(self.batches.list_recent(), ())

    def test_quarantined_retained_dataset_is_rejected_before_any_batch_is_saved(self) -> None:
        gappy = self._dataset(gap=True)
        gappy_service = RetainedDatasetBacktestService(
            MemoryCandleRepository((gappy,)), self.batches, self.manifests
        )

        with self.assertRaises(ResearchDatasetValidationError):
            gappy_service.run(self._request(gappy.dataset_id), now=self.start)
        self.assertEqual(self.batches.list_recent(), ())


if __name__ == "__main__":
    unittest.main()
