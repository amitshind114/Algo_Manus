from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from algo_manus.application.market_data import MarketDataRequest, MarketDataService
from algo_manus.application.retained_dataset_backtesting import (
    ApprovedResearchSourcePolicy,
    RetainedDatasetBacktestRequest,
    RetainedDatasetBacktestService,
)
from algo_manus.domain.market_data import DataUseCase
from algo_manus.infrastructure.market_data.dhan_historical import DhanHistoricalCandleProvider
from algo_manus.infrastructure.market_data.sqlite_repository import SqliteCandleDatasetRepository
from algo_manus.infrastructure.experiments.sqlite_repository import SqliteExperimentBatchRepository
from algo_manus.infrastructure.research import SqliteResearchEvidenceRepository


class DhanRetainedBacktestingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.start = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)
        self.end = self.start + timedelta(days=5)
        self.retrieved_at = self.end + timedelta(hours=1)
        self.instrument_id = "DHAN:NSE_EQ:1333"
        self.database_path = Path(self.temp_dir.name) / "dhan_datasets.sqlite3"
        self.batches = SqliteExperimentBatchRepository(
            Path(self.temp_dir.name) / "experiments.sqlite3"
        )
        self.manifests = SqliteResearchEvidenceRepository(
            Path(self.temp_dir.name) / "research.sqlite3"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _payload(self) -> dict:
        base = int(self.start.timestamp())
        return {
            "open": [100.0, 101.0, 100.0, 102.0, 104.0, 103.0, 101.0, 99.0, 98.0],
            "high": [102.0, 103.0, 102.0, 105.0, 106.0, 104.0, 102.0, 100.0, 99.0],
            "low": [99.0, 100.0, 99.0, 101.0, 103.0, 102.0, 100.0, 98.0, 97.0],
            "close": [101.0, 102.0, 101.0, 104.0, 105.0, 103.0, 101.0, 99.0, 98.0],
            "volume": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800],
            "timestamp": [base + index * 300 for index in range(9)],
        }

    def _provider(self) -> DhanHistoricalCandleProvider:
        encoded = json.dumps(self._payload()).encode("utf-8")

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            return encoded

        return DhanHistoricalCandleProvider(
            credentials=type("Credentials", (), {"access_token": "test-token"})(),
            transport=transport,
        )

    def _persist_dataset(self) -> str:
        repository = SqliteCandleDatasetRepository(self.database_path)
        service = MarketDataService(repository)
        dataset = service.ingest(
            self._provider(),
            MarketDataRequest(
                instrument_id=self.instrument_id,
                interval="5m",
                start=self.start,
                end=self.end,
                use_case=DataUseCase.RESEARCH,
            ),
            retrieved_at=self.retrieved_at,
        )
        return dataset.dataset_id

    def _request(self, dataset_id: str) -> RetainedDatasetBacktestRequest:
        return RetainedDatasetBacktestRequest(
            dataset_id=dataset_id,
            strategy_id="sma_crossover",
            parameters={"fast_window": 2, "slow_window": 3},
            initial_cash=1_000,
            quantity=10,
            commission_bps=0,
            slippage_bps=0,
        )

    def test_dhan_dataset_flows_through_retained_backtesting_with_lineage(self) -> None:
        dataset_id = self._persist_dataset()
        candle_repository = SqliteCandleDatasetRepository(self.database_path)
        service = RetainedDatasetBacktestService(
            candle_repository,
            self.batches,
            self.manifests,
            policy=ApprovedResearchSourcePolicy.for_dhan_research(),
        )
        created_at = self.retrieved_at + timedelta(hours=1)

        run = service.run(self._request(dataset_id), now=created_at)
        stored_batch = self.batches.get(run.batch.batch_id)
        manifest = self.manifests.get(run.batch.research_manifest_id or "")

        self.assertEqual(run.dataset.dataset_id, dataset_id)
        self.assertEqual(run.dataset.provenance.source_name, "dhan")
        self.assertTrue(run.validation.research_eligible)
        self.assertIsNotNone(stored_batch)
        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest.lineages[0].dataset_id, dataset_id)
        self.assertEqual(
            manifest.lineages[0].raw_content_sha256,
            run.dataset.provenance.raw_content_sha256,
        )
        self.assertEqual(
            manifest.information_cutoff,
            run.dataset.candles[-1].timestamp,
        )
        self.assertEqual(
            run.batch.universe_snapshot_id,
            f"DATASET:{dataset_id}",
        )
        self.assertTrue(
            all(
                trade.entry_time > run.dataset.candles[2].timestamp
                for trade in run.batch.results[0].backtest.trades
            )
        )

    def test_default_angel_only_policy_still_rejects_dhan_dataset(self) -> None:
        dataset_id = self._persist_dataset()
        candle_repository = SqliteCandleDatasetRepository(self.database_path)
        service = RetainedDatasetBacktestService(
            candle_repository,
            self.batches,
            self.manifests,
        )

        with self.assertRaisesRegex(ValueError, "approved by the research source policy"):
            service.run(self._request(dataset_id), now=self.retrieved_at)
        self.assertEqual(self.batches.list_recent(), ())


if __name__ == "__main__":
    unittest.main()
