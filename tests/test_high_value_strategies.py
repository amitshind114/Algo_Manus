from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService

from algo_manus.domain.market_data import Candle
from algo_manus.domain.strategy import SignalAction
from algo_manus.strategies import built_in_registry


class HighValueStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        start = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
        closes = (100, 99, 98, 99, 101, 103, 105, 103, 100, 98, 96, 98, 101, 104, 106)
        self.candles = tuple(
            Candle(
                timestamp=start + timedelta(days=index),
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=1_000,
            )
            for index, close in enumerate(closes)
        )

    def test_registry_exposes_selected_high_value_families(self) -> None:
        ids = {item.strategy_id for item in built_in_registry().metadata()}
        self.assertEqual(ids, {
            "sma_crossover", "ema_crossover", "rsi_mean_reversion", "rsi_threshold_reversion",
            "macd_signal", "bollinger_breakout", "triple_ema_crossover",
        })

    def test_selected_strategies_validate_and_return_signal_actions(self) -> None:
        registry = built_in_registry()
        cases = {
            "ema_crossover": {"fast_window": 3, "slow_window": 6},
            "rsi_mean_reversion": {"rsi_window": 5, "oversold": 30.0, "overbought": 70.0},
            "macd_signal": {"fast_window": 3, "slow_window": 6, "signal_window": 2},
            "bollinger_breakout": {"window": 5, "deviation": 2.0},
            "triple_ema_crossover": {"fast_window": 3, "middle_window": 5, "slow_window": 8},
        }
        for strategy_id, parameters in cases.items():
            registry.validate_parameters(strategy_id, parameters)
            strategy = registry.get(strategy_id)
            self.assertGreater(strategy.required_history(parameters), 0)
            self.assertIn(strategy.signal(self.candles, parameters), tuple(SignalAction))

    def test_selected_strategy_runs_through_fixture_experiment_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            batch = FixtureWorkbenchService(Path(directory)).run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                strategy_id="ema_crossover",
                parameters={"fast_window": 3, "slow_window": 6},
                initial_cash=100_000.0,
                quantity=100,
                commission_bps=10.0,
                slippage_bps=5.0,
            )
        self.assertEqual(batch.strategy_id, "ema_crossover")
        self.assertEqual(len(batch.results), 1)
        self.assertIsNotNone(batch.results[0].backtest.outcome)
        self.assertGreaterEqual(batch.results[0].backtest.outcome.required_history, 7)

    def test_cross_field_validation_rejects_invalid_ordering(self) -> None:
        registry = built_in_registry()
        with self.assertRaisesRegex(ValueError, "smaller"):
            registry.validate_parameters("ema_crossover", {"fast_window": 6, "slow_window": 3})
        with self.assertRaisesRegex(ValueError, "ordered"):
            registry.validate_parameters("triple_ema_crossover", {"fast_window": 8, "middle_window": 5, "slow_window": 4})
        with self.assertRaisesRegex(ValueError, "oversold"):
            registry.validate_parameters("rsi_mean_reversion", {"rsi_window": 5, "oversold": 75.0, "overbought": 70.0})


if __name__ == "__main__":
    unittest.main()

# Pure local strategies only: no provider, database, credential, account, order or execution access.
# End.
