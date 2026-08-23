from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService


class EvidenceHealthTests(unittest.TestCase):
    def test_empty_persisted_store_reports_zero_health_coverage(self) -> None:
        with TemporaryDirectory() as directory:
            health = FixtureWorkbenchService(Path(directory)).evidence_health()

            self.assertEqual(health.total_result_count, 0)
            self.assertEqual(health.complete_count, 0)
            self.assertEqual(health.unavailable_count, 0)
            self.assertEqual(health.incomplete_count, 0)
            self.assertEqual(health.result_spec_mismatch_count, 0)

    def test_complete_persisted_store_aggregates_artifact_health_after_restart(self) -> None:
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

            health = FixtureWorkbenchService(root).evidence_health()

            self.assertEqual(health.total_result_count, 2)
            self.assertEqual(health.complete_count, 2)
            self.assertEqual(health.non_complete_count, 0)

    def test_spec_mismatch_is_aggregated_without_repairing_the_local_artifact(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            batch = FixtureWorkbenchService(root).run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            with sqlite3.connect(root / "experiments.sqlite3") as connection:
                connection.execute(
                    "UPDATE experiment_result_artifacts SET result_spec_id = 'BT-mismatch' WHERE batch_id = ?",
                    (batch.batch_id,),
                )

            health = FixtureWorkbenchService(root).evidence_health()

            self.assertEqual(health.total_result_count, 1)
            self.assertEqual(health.complete_count, 0)
            self.assertEqual(health.result_spec_mismatch_count, 1)
            self.assertEqual(health.non_complete_count, 1)
