"""Option K acceptance tests for bounded local robustness research evidence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from algo_manus.application.robustness import (
    LocalRobustnessEvaluationService,
    RobustnessGateState,
    RobustnessGrid,
    RobustnessSplitPolicy,
)
from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.infrastructure.robustness.sqlite_repository import SqliteRobustnessEvidenceRepository
from algo_manus.strategies.registry import built_in_registry


def _dataset() -> CandleDataset:
    start = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    closes = (100, 98, 96, 97, 101, 106, 110, 107, 103, 99, 96, 98, 102, 108, 113, 110, 106, 103, 100, 104, 109, 114, 117, 113, 108, 105, 101, 104, 109, 115)
    return CandleDataset.create(
        instrument_id="FIXTURE:NSE:EQ:ALPHA",
        interval="1d",
        provenance=DataProvenance(
            source_name="robustness-fixture",
            source_kind=DataSourceKind.FIXTURE,
            source_uri="fixture://robustness-gate/v1",
            retrieved_at=start,
            raw_content_sha256=sha256(b"robustness-gate").hexdigest(),
            adjustment_basis="synthetic unadjusted fixture bars",
            use_case=DataUseCase.RESEARCH,
        ),
        candles=tuple(
            Candle(
                timestamp=start + timedelta(days=index),
                open=float(close),
                high=float(close + 1),
                low=float(close - 1),
                close=float(close),
                volume=10_000,
            )
            for index, close in enumerate(closes)
        ),
    )


class RobustnessGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = SqliteRobustnessEvidenceRepository(
            Path(self.temp_dir.name) / "robustness.sqlite3"
        )
        self.service = LocalRobustnessEvaluationService(self.repository)
        self.strategy = built_in_registry().get("sma_crossover")
        self.created_at = datetime(2026, 8, 26, 9, 15, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_chronological_split_and_bounded_grid_retain_reproducible_next_bar_evidence(self) -> None:
        grid = RobustnessGrid({"fast_window": (2, 3), "slow_window": (5, 6)})
        policy = RobustnessSplitPolicy(in_sample_ratio=0.6, max_grid_cells=4, embargo_bars=1)

        evidence = self.service.evaluate(
            dataset=_dataset(),
            strategy=self.strategy,
            grid=grid,
            split_policy=policy,
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
            created_at=self.created_at,
        )
        reloaded = SqliteRobustnessEvidenceRepository(
            Path(self.temp_dir.name) / "robustness.sqlite3"
        ).get(evidence.evidence_id)

        self.assertEqual(evidence.gate_state, RobustnessGateState.INFORMATIONAL_ONLY)
        self.assertEqual(evidence.in_sample_end, _dataset().candles[17].timestamp)
        self.assertEqual(evidence.holdout_start, _dataset().candles[19].timestamp)
        self.assertEqual(len(evidence.candidates), 4)
        self.assertTrue(all(item.parameter_revision_id.startswith("PARAM-") for item in evidence.candidates))
        self.assertEqual(evidence.initial_cash, 100_000)
        self.assertEqual(evidence.quantity, 100)
        self.assertEqual(evidence.commission_bps, 10)
        self.assertEqual(evidence.slippage_bps, 5)
        self.assertTrue(evidence.force_close_at_end)
        self.assertTrue(all(item.in_sample.result_spec_id != item.holdout.result_spec_id for item in evidence.candidates))
        self.assertTrue(all(item.in_sample.next_bar_execution and item.holdout.next_bar_execution for item in evidence.candidates))
        self.assertIn("selection bias", evidence.selection_bias_warning.lower())
        self.assertEqual(reloaded, evidence)

        replayed = LocalRobustnessEvaluationService(
            SqliteRobustnessEvidenceRepository(Path(self.temp_dir.name) / "robustness.sqlite3")
        ).evaluate(
            dataset=_dataset(),
            strategy=self.strategy,
            grid=grid,
            split_policy=policy,
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
            created_at=self.created_at + timedelta(days=1),
        )
        self.assertEqual(replayed, evidence)

    def test_split_policy_censors_declared_embargo_bars_from_both_partitions(self) -> None:
        evidence = self.service.evaluate(
            dataset=_dataset(),
            strategy=self.strategy,
            grid=RobustnessGrid({"fast_window": (2,), "slow_window": (5,)}),
            split_policy=RobustnessSplitPolicy(in_sample_ratio=0.6, max_grid_cells=4, embargo_bars=2),
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
            created_at=self.created_at,
        )

        self.assertEqual(evidence.in_sample_end, _dataset().candles[17].timestamp)
        self.assertEqual(evidence.holdout_start, _dataset().candles[20].timestamp)
        self.assertEqual(evidence.split_policy.embargo_bars, 2)

    def test_grid_rejects_unknown_invalid_or_excessive_parameter_cells_before_evaluation(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown parameter"):
            self.service.evaluate(
                dataset=_dataset(), strategy=self.strategy,
                grid=RobustnessGrid({"unknown": (1,)}),
                split_policy=RobustnessSplitPolicy(in_sample_ratio=0.6, max_grid_cells=4),
                initial_cash=100_000, quantity=100, commission_bps=10, slippage_bps=5,
                created_at=self.created_at,
            )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.service.evaluate(
                dataset=_dataset(), strategy=self.strategy,
                grid=RobustnessGrid({"fast_window": (2, 3, 4), "slow_window": (5, 6)}),
                split_policy=RobustnessSplitPolicy(in_sample_ratio=0.6, max_grid_cells=4),
                initial_cash=100_000, quantity=100, commission_bps=10, slippage_bps=5,
                created_at=self.created_at,
            )

    def test_insufficient_partition_history_is_retained_as_non_promotable_evidence(self) -> None:
        short = CandleDataset.create(
            instrument_id="FIXTURE:NSE:EQ:SHORT",
            interval="1d",
            provenance=_dataset().provenance,
            candles=_dataset().candles[:8],
        )

        evidence = self.service.evaluate(
            dataset=short,
            strategy=self.strategy,
            grid=RobustnessGrid({"fast_window": (3,), "slow_window": (6,)}),
            split_policy=RobustnessSplitPolicy(in_sample_ratio=0.6, max_grid_cells=4),
            initial_cash=100_000, quantity=100, commission_bps=10, slippage_bps=5,
            created_at=self.created_at,
        )

        self.assertEqual(evidence.gate_state, RobustnessGateState.INSUFFICIENT_HISTORY)
        self.assertEqual(len(evidence.candidates), 1)
        self.assertIsNone(evidence.candidates[0].in_sample)
        self.assertIsNone(evidence.candidates[0].holdout)
        self.assertFalse(hasattr(evidence, "promote"))
        self.assertFalse(hasattr(self.service, "submit"))
        self.assertFalse(hasattr(self.service, "download"))


if __name__ == "__main__":
    unittest.main()
