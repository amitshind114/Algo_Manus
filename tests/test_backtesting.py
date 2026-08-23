from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.domain.backtest import BacktestSpec
from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.domain.strategy import StrategyParameterRevision
from algo_manus.strategies.sma_crossover import SmaCrossoverStrategy


class BacktestTests(unittest.TestCase):
    def test_spec_identity_normalizes_equivalent_numeric_inputs(self) -> None:
        integer_form = BacktestSpec(
            dataset_id="dataset",
            strategy_id="strategy",
            parameter_revision_id="revision",
            initial_cash=1_000,
            quantity=10,
            commission_bps=0,
            slippage_bps=0,
        )
        persisted_form = BacktestSpec(
            dataset_id="dataset",
            strategy_id="strategy",
            parameter_revision_id="revision",
            initial_cash=1_000.0,
            quantity=10.0,
            commission_bps=0.0,
            slippage_bps=0.0,
        )

        self.assertEqual(integer_form.spec_id, persisted_form.spec_id)

    def _dataset(self) -> CandleDataset:
        start = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)
        closes = [10, 9, 8, 9, 11, 13, 12, 10, 8]
        candles = tuple(
            Candle(
                timestamp=start + timedelta(days=index),
                open=close - 0.25,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=1000,
            )
            for index, close in enumerate(closes)
        )
        return CandleDataset.create(
            instrument_id="ANGEL_ONE:NSE:NSE:500325",
            interval="1d",
            provenance=DataProvenance(
                source_name="fixture-research",
                source_kind=DataSourceKind.FIXTURE,
                source_uri="fixture://research/candles",
                retrieved_at=start,
                raw_content_sha256=sha256(b"backtest-fixture-v1").hexdigest(),
                adjustment_basis="unadjusted fixture bars",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=candles,
        )

    def test_sma_backtest_fills_on_next_bar_and_preserves_spec_lineage(self) -> None:
        dataset = self._dataset()
        strategy = SmaCrossoverStrategy()
        parameters = StrategyParameterRevision.create(
            "sma_crossover", {"fast_window": 2, "slow_window": 3}
        )
        spec = BacktestSpec(
            dataset_id=dataset.dataset_id,
            strategy_id=strategy.strategy_id,
            parameter_revision_id=parameters.revision_id,
            initial_cash=1_000,
            quantity=10,
            commission_bps=10,
            slippage_bps=5,
        )

        result = BarBacktestService().run(
            dataset=dataset, strategy=strategy, parameters=parameters, spec=spec
        )

        self.assertEqual(result.spec.spec_id, spec.spec_id)
        self.assertEqual(result.metrics.trade_count, 1)
        self.assertGreater(result.trades[0].entry_time, dataset.candles[3].timestamp)
        self.assertNotEqual(result.trades[0].entry_price, dataset.candles[4].open)
        self.assertTrue(result.equity_curve)

    def test_backtest_rejects_paper_dataset(self) -> None:
        dataset = self._dataset()
        paper_dataset = CandleDataset.create(
            instrument_id=dataset.instrument_id,
            interval=dataset.interval,
            provenance=DataProvenance(
                source_name="fixture-broker",
                source_kind=DataSourceKind.BROKER,
                source_uri="fixture://paper/candles",
                retrieved_at=dataset.provenance.retrieved_at,
                raw_content_sha256=sha256(b"paper-fixture").hexdigest(),
                adjustment_basis="unadjusted fixture bars",
                use_case=DataUseCase.PAPER,
            ),
            candles=dataset.candles,
        )
        strategy = SmaCrossoverStrategy()
        parameters = StrategyParameterRevision.create(
            "sma_crossover", {"fast_window": 2, "slow_window": 3}
        )
        spec = BacktestSpec(
            dataset_id=paper_dataset.dataset_id,
            strategy_id=strategy.strategy_id,
            parameter_revision_id=parameters.revision_id,
            initial_cash=1_000,
            quantity=1,
            commission_bps=0,
            slippage_bps=0,
        )

        with self.assertRaisesRegex(ValueError, "research-use"):
            BarBacktestService().run(
                dataset=paper_dataset, strategy=strategy, parameters=parameters, spec=spec
            )


if __name__ == "__main__":
    unittest.main()
