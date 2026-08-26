from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from algo_manus.application.demo_workbench import FIXTURE_MODE_LABEL, FixtureWorkbenchService
from algo_manus.application.leaderboard import LeaderboardSort
from algo_manus.ui.workbench import leaderboard_sort_options


class FixtureWorkbenchTests(unittest.TestCase):
    def test_fixture_workbench_runs_selected_universe_through_experiment_service(self) -> None:
        service = FixtureWorkbenchService()
        selected = tuple(item.instrument_id for item in service.instruments()[:3])
        batch = service.run_experiment(
            selected_instrument_ids=selected,
            fast_window=3,
            slow_window=6,
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
        )
        rows = service.leaderboard(batch, LeaderboardSort.NET_PNL)

        self.assertIn("not broker", FIXTURE_MODE_LABEL)
        self.assertEqual(len(batch.results), 3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(item.backtest.spec.strategy_id == "sma_crossover" for item in batch.results))

    def test_fixture_input_rejects_invalid_sma_windows(self) -> None:
        service = FixtureWorkbenchService()
        with self.assertRaisesRegex(ValueError, "fast window"):
            service.run_experiment(
                selected_instrument_ids=(service.instruments()[0].instrument_id,),
                fast_window=6,
                slow_window=6,
                initial_cash=100_000,
                quantity=100,
                commission_bps=10,
                slippage_bps=5,
            )

    def test_leaderboard_sort_options_resolve_without_streamlit(self) -> None:
        options = leaderboard_sort_options()

        self.assertEqual(options["Net P&L"], LeaderboardSort.NET_PNL)
        self.assertEqual(options["Return"], LeaderboardSort.TOTAL_RETURN)
        self.assertEqual(options["Drawdown"], LeaderboardSort.MAX_DRAWDOWN)

    def test_workbench_retains_safe_local_robustness_evidence_without_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = FixtureWorkbenchService(data_root=Path(directory))
            evidence = service.run_local_robustness_evaluation(
                instrument_id="FIXTURE:NSE:EQ:ALPHA"
            )
            restarted = FixtureWorkbenchService(data_root=Path(directory))

            recent = restarted.recent_robustness_evidence()

        self.assertEqual(evidence.gate_state.value, "INFORMATIONAL_ONLY")
        self.assertEqual(recent, (evidence,))
        self.assertFalse(hasattr(service, "promote_robustness"))


if __name__ == "__main__":
    unittest.main()
