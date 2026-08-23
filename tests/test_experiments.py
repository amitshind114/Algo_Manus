from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.application.experiments import BatchBacktestRequest, ExperimentBatchService
from algo_manus.application.leaderboard import LeaderboardService, LeaderboardSort
from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.domain.strategy import StrategyParameterRevision
from algo_manus.infrastructure.experiments.sqlite_repository import SqliteExperimentBatchRepository
from algo_manus.strategies.sma_crossover import SmaCrossoverStrategy


class ExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = SqliteExperimentBatchRepository(Path(self.temp_dir.name) / "experiments.sqlite3")
        self.start = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _dataset(self, instrument_id: str, closes: list[float]) -> CandleDataset:
        candles = tuple(
            Candle(
                timestamp=self.start + timedelta(days=index),
                open=close - 0.2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=1000,
            )
            for index, close in enumerate(closes)
        )
        return CandleDataset.create(
            instrument_id=instrument_id,
            interval="1d",
            provenance=DataProvenance(
                source_name="fixture-research",
                source_kind=DataSourceKind.FIXTURE,
                source_uri="fixture://experiments/candles",
                retrieved_at=self.start,
                raw_content_sha256=sha256(instrument_id.encode()).hexdigest(),
                adjustment_basis="unadjusted fixture bars",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=candles,
        )

    def test_multi_security_batch_persists_and_leaderboard_sorts_results(self) -> None:
        first_id = "ANGEL_ONE:NSE:NSE:500325"
        second_id = "ANGEL_ONE:NSE:NSE:532540"
        request = BatchBacktestRequest(
            universe_id="selected-equities",
            universe_snapshot_id="ANGEL_ONE-20260823-fixture",
            datasets_by_instrument={
                first_id: self._dataset(first_id, [10, 9, 8, 9, 11, 14, 13, 10, 8]),
                second_id: self._dataset(second_id, [10, 9, 8, 9, 10, 11, 10, 9, 8]),
            },
            initial_cash=1_000,
            quantity=10,
            commission_bps=0,
            slippage_bps=0,
        )
        parameters = StrategyParameterRevision.create(
            "sma_crossover", {"fast_window": 2, "slow_window": 3}
        )
        batch = ExperimentBatchService(BarBacktestService(), self.repository).run(
            request=request,
            strategy=SmaCrossoverStrategy(),
            parameters=parameters,
            created_at=self.start,
        )

        restored = self.repository.get(batch.batch_id)
        rows = LeaderboardService().rows(batch, LeaderboardSort.NET_PNL)

        self.assertIsNotNone(restored)
        self.assertEqual(len(restored.results), 2)
        self.assertGreaterEqual(rows[0].net_pnl, rows[1].net_pnl)
        expected_specs = {
            item.instrument_id: item.backtest.spec.spec_id
            for item in batch.results
        }
        self.assertEqual(rows[0].result_spec_id, expected_specs[rows[0].instrument_id])
        self.assertEqual(
            {item.backtest.spec.spec_id for item in restored.results},
            set(expected_specs.values()),
        )


if __name__ == "__main__":
    unittest.main()
