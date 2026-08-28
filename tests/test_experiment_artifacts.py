from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService
from algo_manus.application.experiments import (
    ExperimentArtifactIntegrityStatus,
    ExperimentArtifactsUnavailableError,
)
from algo_manus.infrastructure.experiments.sqlite_repository import SqliteExperimentBatchRepository
from tests.sqlite_test_utils import closed_sqlite_connection


class ExperimentArtifactTests(unittest.TestCase):
    def test_detailed_fixture_artifacts_round_trip_after_service_restart(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = FixtureWorkbenchService(root)
            batch = first.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            expected = batch.results[0].backtest

            recovered = FixtureWorkbenchService(root).experiment_artifacts(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
            )

            self.assertEqual(recovered.batch_id, batch.batch_id)
            self.assertEqual(recovered.instrument_id, "FIXTURE:NSE:EQ:ALPHA")
            self.assertEqual(recovered.result_spec_id, expected.spec.spec_id)
            self.assertEqual(recovered.trades, expected.trades)
            self.assertEqual(recovered.equity_curve, expected.equity_curve)

    def test_missing_legacy_artifacts_fail_explicitly(self) -> None:
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
            with closed_sqlite_connection(root / "experiments.sqlite3") as connection:
                connection.execute("DELETE FROM experiment_equity_points WHERE batch_id = ?", (batch.batch_id,))
                connection.execute("DELETE FROM experiment_trades WHERE batch_id = ?", (batch.batch_id,))
                connection.execute("DELETE FROM experiment_result_artifacts WHERE batch_id = ?", (batch.batch_id,))

            with self.assertRaises(ExperimentArtifactsUnavailableError):
                FixtureWorkbenchService(root).experiment_artifacts(
                    batch_id=batch.batch_id,
                    instrument_id="FIXTURE:NSE:EQ:ALPHA",
                )

    def test_configured_artifact_retention_limit_rejects_oversized_result(self) -> None:
        batch = FixtureWorkbenchService().run_experiment(
            selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
            fast_window=3,
            slow_window=6,
            initial_cash=100_000,
            quantity=10,
            commission_bps=1.0,
            slippage_bps=1.0,
        )
        with TemporaryDirectory() as directory:
            repository = SqliteExperimentBatchRepository(
                Path(directory) / "experiments.sqlite3",
                max_equity_points_per_result=1,
            )

            with self.assertRaisesRegex(ValueError, "equity point retention limit"):
                repository.save(batch)

    def test_integrity_status_reports_complete_local_artifacts_after_restart(self) -> None:
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

            integrity = FixtureWorkbenchService(root).experiment_artifact_integrity(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
            )

            self.assertEqual(integrity.status, ExperimentArtifactIntegrityStatus.COMPLETE)
            self.assertTrue(integrity.is_complete)
            self.assertEqual(
                integrity.actual_equity_point_count,
                len(batch.results[0].backtest.equity_curve),
            )
            self.assertEqual(integrity.actual_trade_count, len(batch.results[0].backtest.trades))

    def test_integrity_status_detects_unavailable_incomplete_and_spec_mismatch(self) -> None:
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
            arguments = {"batch_id": batch.batch_id, "instrument_id": "FIXTURE:NSE:EQ:ALPHA"}
            database = root / "experiments.sqlite3"

            with closed_sqlite_connection(database) as connection:
                connection.execute("DELETE FROM experiment_result_artifacts WHERE batch_id = ?", (batch.batch_id,))
            unavailable = FixtureWorkbenchService(root).experiment_artifact_integrity(**arguments)
            self.assertEqual(unavailable.status, ExperimentArtifactIntegrityStatus.UNAVAILABLE)

            FixtureWorkbenchService(root).run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=20,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            with closed_sqlite_connection(database) as connection:
                batch_id = connection.execute(
                    "SELECT batch_id FROM experiment_batches ORDER BY created_at DESC LIMIT 1"
                ).fetchone()[0]
                connection.execute(
                    "DELETE FROM experiment_equity_points WHERE batch_id = ? AND sequence = 0", (batch_id,)
                )
            incomplete = FixtureWorkbenchService(root).experiment_artifact_integrity(
                batch_id=batch_id, instrument_id="FIXTURE:NSE:EQ:ALPHA"
            )
            self.assertEqual(incomplete.status, ExperimentArtifactIntegrityStatus.INCOMPLETE)

            with closed_sqlite_connection(database) as connection:
                connection.execute(
                    "UPDATE experiment_result_artifacts SET result_spec_id = 'BT-mismatch' WHERE batch_id = ?",
                    (batch_id,),
                )
            mismatch = FixtureWorkbenchService(root).experiment_artifact_integrity(
                batch_id=batch_id, instrument_id="FIXTURE:NSE:EQ:ALPHA"
            )
            self.assertEqual(mismatch.status, ExperimentArtifactIntegrityStatus.RESULT_SPEC_MISMATCH)
            with self.assertRaisesRegex(ValueError, "integrity status"):
                FixtureWorkbenchService(root).experiment_artifacts(
                    batch_id=batch_id, instrument_id="FIXTURE:NSE:EQ:ALPHA"
                )
