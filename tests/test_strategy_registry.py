from __future__ import annotations

from datetime import datetime, timezone
import unittest

from algo_manus.domain.strategy import ParameterValidationError, StrategyContext
from algo_manus.strategies import (
    SmaCrossoverStrategy,
    StrategyCompatibilityError,
    StrategyNotRegisteredError,
    StrategyRegistry,
    built_in_registry,
)


class StrategyRegistryTests(unittest.TestCase):
    def test_builtin_registry_exposes_versioned_sma_metadata(self) -> None:
        registry = built_in_registry()

        metadata = registry.metadata()

        self.assertEqual(
            {item.strategy_id for item in metadata},
            {
                "sma_crossover",
                "ema_crossover",
                "rsi_mean_reversion",
                "macd_signal",
                "bollinger_breakout",
                "triple_ema_crossover",
            },
        )
        sma = next(item for item in metadata if item.strategy_id == "sma_crossover")
        self.assertEqual(sma.version, "1.0.0")
        self.assertEqual(sma.parameter_schema.defaults(), {"fast_window": 3, "slow_window": 6})

    def test_registry_validates_strict_sma_parameters(self) -> None:
        registry = built_in_registry()

        validated = registry.validate_parameters(
            "sma_crossover", {"fast_window": 3, "slow_window": 6}
        )

        self.assertEqual(validated, {"fast_window": 3, "slow_window": 6})
        with self.assertRaisesRegex(ParameterValidationError, "smaller"):
            registry.validate_parameters("sma_crossover", {"fast_window": 6, "slow_window": 6})
        with self.assertRaisesRegex(ParameterValidationError, "unknown"):
            registry.validate_parameters(
                "sma_crossover", {"fast_window": 3, "slow_window": 6, "ignored": 1}
            )
        with self.assertRaisesRegex(ParameterValidationError, "integer"):
            registry.validate_parameters("sma_crossover", {"fast_window": 3.5, "slow_window": 6})

    def test_registry_enforces_registration_and_compatibility(self) -> None:
        registry = StrategyRegistry([SmaCrossoverStrategy()])

        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(SmaCrossoverStrategy())
        with self.assertRaisesRegex(StrategyNotRegisteredError, "not registered"):
            registry.get("unknown")
        registry.validate_compatibility("sma_crossover", instrument_type="EQUITY", interval="1d")
        with self.assertRaisesRegex(StrategyCompatibilityError, "interval"):
            registry.validate_compatibility("sma_crossover", instrument_type="EQUITY", interval="5m")
        with self.assertRaisesRegex(StrategyCompatibilityError, "instrument type"):
            registry.validate_compatibility("sma_crossover", instrument_type="OPTION", interval="1d")

    def test_strategy_context_is_timezone_aware_and_read_only(self) -> None:
        context = StrategyContext(
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            instrument_type="EQUITY",
            interval="1d",
            candles=(),
            portfolio_state={"cash": 100_000},
            as_of=datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc),
        )

        self.assertEqual(context.instrument_type, "EQUITY")
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            StrategyContext(
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                instrument_type="EQUITY",
                interval="1d",
                candles=(),
                portfolio_state={},
                as_of=datetime(2026, 8, 23, 9, 15),
            )


if __name__ == "__main__":
    unittest.main()
