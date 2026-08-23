from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService


class EvidenceHealthScopeTests(unittest.TestCase):
    def test_all_scope_batch_scope_and_inclusive_time_range_are_restart_safe(self) -> None:
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
            restarted = FixtureWorkbenchService(root)

            all_scope = restarted.evidence_health_scope()
            batch_scope = restarted.evidence_health_scope(batch_id=first.batch_id)
            time_scope = restarted.evidence_health_scope(
                created_from=second.created_at,
                created_until=second.created_at,
            )

            self.assertEqual(all_scope.health.total_result_count, 3)
            self.assertEqual(tuple(item.batch_id for item in all_scope.history), (first.batch_id, second.batch_id))
            self.assertEqual(batch_scope.health.total_result_count, 1)
            self.assertEqual(tuple(item.batch_id for item in batch_scope.history), (first.batch_id,))
            self.assertEqual(time_scope.health.total_result_count, 2)
            self.assertEqual(tuple(item.batch_id for item in time_scope.history), (second.batch_id,))

    def test_invalid_time_bounds_and_unknown_batch_fail_without_mutation(self) -> None:
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
            restarted = FixtureWorkbenchService(root)

            with self.assertRaises(ValueError):
                restarted.evidence_health_scope(
                    created_from=batch.created_at + timedelta(seconds=1),
                    created_until=batch.created_at,
                )
            with self.assertRaises(ValueError):
                restarted.evidence_health_scope(batch_id="EXP-unknown")

            self.assertEqual(restarted.evidence_health_scope().health.total_result_count, 1)
