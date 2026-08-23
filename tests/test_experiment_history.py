from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService


class ExperimentHistoryTests(unittest.TestCase):
    def test_persisted_fixture_experiments_list_after_service_restart(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = FixtureWorkbenchService(root)
            batch = first.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA", "FIXTURE:NSE:EQ:BRAVO"),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )

            recovered = FixtureWorkbenchService(root).recent_experiments()

            self.assertEqual([item.batch_id for item in recovered], [batch.batch_id])
            self.assertEqual(recovered[0].research_manifest_id, batch.research_manifest_id)
            self.assertEqual(len(recovered[0].results), 2)

    def test_recent_history_rejects_non_positive_limit(self) -> None:
        with self.assertRaises(ValueError):
            FixtureWorkbenchService().recent_experiments(0)
