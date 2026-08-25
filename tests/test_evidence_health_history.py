from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService
from tests.sqlite_test_utils import closed_sqlite_connection


class EvidenceHealthHistoryTests(unittest.TestCase):
    def test_empty_persisted_store_has_no_health_history(self) -> None:
        with TemporaryDirectory() as directory:
            history = FixtureWorkbenchService(Path(directory)).evidence_health_history()

            self.assertEqual(history, ())

    def test_history_orders_saved_batches_by_creation_time_and_aggregates_statuses_after_restart(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            service = FixtureWorkbenchService(root)
            first = service.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            second = service.run_experiment(
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
                    (second.batch_id,),
                )

            history = FixtureWorkbenchService(root).evidence_health_history()

            self.assertEqual([item.batch_id for item in history], [first.batch_id, second.batch_id])
            self.assertLessEqual(history[0].created_at, history[1].created_at)
            self.assertEqual(history[0].total_result_count, 1)
            self.assertEqual(history[0].complete_count, 1)
            self.assertEqual(history[1].total_result_count, 2)
            self.assertEqual(history[1].result_spec_mismatch_count, 2)
            self.assertEqual(history[1].non_complete_count, 2)
