from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService
from tests.sqlite_test_utils import closed_sqlite_connection


class EvidenceHealthComparisonTests(unittest.TestCase):
    def test_comparison_is_restart_safe_and_exposes_right_minus_left_count_deltas(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            service = FixtureWorkbenchService(root)
            complete = service.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            non_complete = service.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:BRAVO", "FIXTURE:NSE:EQ:CEDAR"),
                fast_window=4,
                slow_window=8,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            with closed_sqlite_connection(root / "experiments.sqlite3") as connection:
                connection.execute(
                    "UPDATE experiment_result_artifacts SET result_spec_id = 'BT-mismatch' WHERE batch_id = ?",
                    (non_complete.batch_id,),
                )
            restarted = FixtureWorkbenchService(root)

            comparison = restarted.evidence_health_comparison(
                left_batch_id=complete.batch_id,
                right_batch_id=non_complete.batch_id,
            )
            reversed_comparison = restarted.evidence_health_comparison(
                left_batch_id=non_complete.batch_id,
                right_batch_id=complete.batch_id,
            )

            self.assertEqual(comparison.left.health.complete_count, 1)
            self.assertEqual(comparison.right.health.result_spec_mismatch_count, 2)
            self.assertEqual(comparison.delta.total_result_count, 1)
            self.assertEqual(comparison.delta.complete_count, -1)
            self.assertEqual(comparison.delta.result_spec_mismatch_count, 2)
            self.assertEqual(reversed_comparison.delta.total_result_count, -1)
            self.assertEqual(reversed_comparison.delta.complete_count, 1)
            self.assertEqual(reversed_comparison.delta.result_spec_mismatch_count, -2)

    def test_same_or_unknown_retained_batch_cannot_be_compared(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            service = FixtureWorkbenchService(root)
            batch = service.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            with self.assertRaises(ValueError):
                service.evidence_health_comparison(
                    left_batch_id=batch.batch_id,
                    right_batch_id=batch.batch_id,
                )
            with self.assertRaises(ValueError):
                service.evidence_health_comparison(
                    left_batch_id=batch.batch_id,
                    right_batch_id="EXP-unknown",
                )
