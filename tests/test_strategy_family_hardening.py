"""Option J acceptance tests for conservative local strategy-family hardening."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.application.demo_workbench import FixtureWorkbenchService
from algo_manus.domain.backtest import BacktestSpec
from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.domain.strategy import StrategyParameterRevision
from algo_manus.strategies.registry import built_in_registry


class StrategyFamilyHardeningTests(unittest.TestCase):
    """Keep the second strategy deterministic, research-only, and promotion-compatible."""

    def test_registry_exposes_versioned_rsi_threshold_reversion_with_strict_threshold_validation(self) -> None:
        registry = built_in_registry()
        metadata = next(item for item in registry.metadata() if item.strategy_id == "rsi_threshold_reversion")

        self.assertEqual(metadata.version, "1.0.0")
        self.assertEqual(metadata.supported_instrument_types, ("EQUITY",))
        self.assertEqual(metadata.supported_intervals, ("1d",))
        self.assertEqual(
            registry.validate_parameters(
                "rsi_threshold_reversion",
                {"rsi_window": 5, "entry_threshold": 30, "exit_threshold": 70},
            ),
            {"rsi_window": 5, "entry_threshold": 30.0, "exit_threshold": 70.0},
        )
        with self.assertRaisesRegex(ValueError, "entry_threshold must be smaller"):
            registry.validate_parameters(
                "rsi_threshold_reversion",
                {"rsi_window": 5, "entry_threshold": 70, "exit_threshold": 70},
            )

    def test_rsi_threshold_reversion_uses_signal_bar_only_and_fills_at_next_open(self) -> None:
        start = datetime(2026, 7, 1, 9, 15, tzinfo=timezone.utc)
        closes = (100.0, 102.0, 104.0, 103.0, 90.0, 85.0, 100.0, 120.0)
        candles = tuple(
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
        dataset = CandleDataset.create(
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            interval="1d",
            provenance=DataProvenance(
                source_name="strategy-family-fixture",
                source_kind=DataSourceKind.FIXTURE,
                source_uri="fixture://strategy-family/no-lookahead",
                retrieved_at=start,
                raw_content_sha256=sha256(b"strategy-family-no-lookahead").hexdigest(),
                adjustment_basis="synthetic unadjusted fixture bars",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=candles,
        )
        parameters = StrategyParameterRevision.create(
            "rsi_threshold_reversion",
            {"rsi_window": 3, "entry_threshold": 30, "exit_threshold": 60},
        )
        spec = BacktestSpec(
            dataset_id=dataset.dataset_id,
            strategy_id="rsi_threshold_reversion",
            parameter_revision_id=parameters.revision_id,
            initial_cash=10_000,
            quantity=1,
            commission_bps=0,
            slippage_bps=0,
        )

        result = BarBacktestService().run(
            dataset=dataset,
            strategy=built_in_registry().get("rsi_threshold_reversion"),
            parameters=parameters,
            spec=spec,
        )

        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].entry_time, candles[5].timestamp)
        self.assertEqual(result.trades[0].entry_price, candles[5].open)
        self.assertEqual(result.trades[0].exit_time, candles[7].timestamp)
        self.assertEqual(result.trades[0].exit_price, candles[7].open)

    def test_family_runs_are_reproducible_comparable_and_paper_promotion_compatible(self) -> None:
        service = FixtureWorkbenchService()
        selected = tuple(item.instrument_id for item in service.instruments()[:2])
        sma = service.run_experiment(
            selected_instrument_ids=selected,
            strategy_id="sma_crossover",
            parameters={"fast_window": 3, "slow_window": 6},
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
        )
        rsi = service.run_experiment(
            selected_instrument_ids=selected,
            strategy_id="rsi_threshold_reversion",
            parameters={"rsi_window": 3, "entry_threshold": 30, "exit_threshold": 70},
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
        )
        rsi_repeat = service.run_experiment(
            selected_instrument_ids=selected,
            strategy_id="rsi_threshold_reversion",
            parameters={"rsi_window": 3, "entry_threshold": 30, "exit_threshold": 70},
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
        )

        comparison = service.strategy_family_comparison(
            left_batch_id=sma.batch_id,
            right_batch_id=rsi.batch_id,
        )
        promotion = service.paper_promotion(batch_id=rsi.batch_id, instrument_id=selected[0])

        self.assertTrue(comparison.is_comparable)
        self.assertEqual({item.strategy_id for item in comparison.members}, {"sma_crossover", "rsi_threshold_reversion"})
        self.assertEqual(comparison.comparison_basis, "same universe, datasets, initial cash, quantity and costs")
        self.assertEqual(
            tuple(item.backtest.metrics for item in rsi.results),
            tuple(item.backtest.metrics for item in rsi_repeat.results),
        )
        self.assertIsNotNone(rsi.research_manifest_id)
        self.assertIsNotNone(promotion)
        self.assertEqual(promotion[0].batch_id, rsi.batch_id)

    def test_comparison_refuses_to_imply_like_for_like_results_when_costs_differ(self) -> None:
        service = FixtureWorkbenchService()
        selected = (service.instruments()[0].instrument_id,)
        left = service.run_experiment(
            selected_instrument_ids=selected,
            strategy_id="sma_crossover",
            parameters={"fast_window": 3, "slow_window": 6},
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
        )
        right = service.run_experiment(
            selected_instrument_ids=selected,
            strategy_id="rsi_threshold_reversion",
            parameters={"rsi_window": 3, "entry_threshold": 30, "exit_threshold": 70},
            initial_cash=100_000,
            quantity=100,
            commission_bps=20,
            slippage_bps=5,
        )

        comparison = service.strategy_family_comparison(
            left_batch_id=left.batch_id,
            right_batch_id=right.batch_id,
        )

        self.assertFalse(comparison.is_comparable)
        self.assertIn("commission_bps", comparison.comparability_reason)
        self.assertFalse(hasattr(comparison, "recommended_strategy_id"))


if __name__ == "__main__":
    unittest.main()
