from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService


class EvidenceLifecycleTests(unittest.TestCase):
    def test_empty_persisted_local_store_reports_zero_read_only_lifecycle_counts(self) -> None:
        with TemporaryDirectory() as directory:
            lifecycle = FixtureWorkbenchService(Path(directory)).evidence_lifecycle()

            self.assertTrue(lifecycle.is_persistent)
            self.assertEqual(lifecycle.batch_count, 0)
            self.assertEqual(lifecycle.result_count, 0)
            self.assertEqual(lifecycle.artifact_count, 0)
            self.assertEqual(lifecycle.completed_trade_count, 0)
            self.assertEqual(lifecycle.equity_point_count, 0)
            self.assertIsNone(lifecycle.oldest_batch_created_at)
            self.assertIsNone(lifecycle.newest_batch_created_at)

    def test_populated_local_store_lifecycle_survives_restart_without_mutation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            FixtureWorkbenchService(root).run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA", "FIXTURE:NSE:EQ:CEDAR"),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )

            lifecycle = FixtureWorkbenchService(root).evidence_lifecycle()

            self.assertTrue(lifecycle.is_persistent)
            self.assertEqual(lifecycle.batch_count, 1)
            self.assertEqual(lifecycle.result_count, 2)
            self.assertEqual(lifecycle.artifact_count, 2)
            self.assertEqual(lifecycle.completed_trade_count, 1)
            self.assertGreater(lifecycle.equity_point_count, 0)
            self.assertGreater(lifecycle.database_size_bytes, 0)
            self.assertIsNotNone(lifecycle.oldest_batch_created_at)
            self.assertEqual(lifecycle.oldest_batch_created_at, lifecycle.newest_batch_created_at)
            self.assertEqual(lifecycle.max_equity_points_per_result, 5_000)
            self.assertEqual(lifecycle.max_trades_per_result, 5_000)
