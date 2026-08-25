from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService
from algo_manus.application.experiments import ExperimentArtifactIntegrityStatus
from tests.sqlite_test_utils import closed_sqlite_connection


class EvidenceHealthDetailTests(unittest.TestCase):
    def test_empty_persisted_store_has_no_health_detail_rows(self) -> None:
        with TemporaryDirectory() as directory:
            details = FixtureWorkbenchService(Path(directory)).evidence_health_details()

            self.assertEqual(details, ())

    def test_health_detail_reports_complete_and_non_complete_rows_after_restart(self) -> None:
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
            unavailable = service.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:BRAVO",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            incomplete = service.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:CEDAR",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            mismatch = service.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=4,
                slow_window=8,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            with closed_sqlite_connection(root / "experiments.sqlite3") as connection:
                connection.execute(
                    "DELETE FROM experiment_result_artifacts WHERE batch_id = ?",
                    (unavailable.batch_id,),
                )
                connection.execute(
                    "DELETE FROM experiment_equity_points WHERE batch_id = ? AND sequence = 0",
                    (incomplete.batch_id,),
                )
                connection.execute(
                    "UPDATE experiment_result_artifacts SET result_spec_id = 'BT-mismatch' WHERE batch_id = ?",
                    (mismatch.batch_id,),
                )

            details = FixtureWorkbenchService(root).evidence_health_details()
            status_by_batch = {item.batch_id: item for item in details}

            self.assertEqual(status_by_batch[complete.batch_id].status, ExperimentArtifactIntegrityStatus.COMPLETE)
            self.assertEqual(status_by_batch[unavailable.batch_id].status, ExperimentArtifactIntegrityStatus.UNAVAILABLE)
            self.assertEqual(status_by_batch[incomplete.batch_id].status, ExperimentArtifactIntegrityStatus.INCOMPLETE)
            self.assertEqual(status_by_batch[mismatch.batch_id].status, ExperimentArtifactIntegrityStatus.RESULT_SPEC_MISMATCH)
            self.assertIsNone(status_by_batch[unavailable.batch_id].expected_trade_count)
            self.assertEqual(status_by_batch[unavailable.batch_id].actual_trade_count, 1)
            self.assertLess(
                status_by_batch[incomplete.batch_id].actual_equity_point_count,
                status_by_batch[incomplete.batch_id].expected_equity_point_count,
            )
