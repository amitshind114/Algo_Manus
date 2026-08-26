"""Option L acceptance tests for the local paper-run evidence gate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService
from algo_manus.application.paper_run_eligibility import (
    PaperRunEligibilityPolicy,
    PaperRunEligibilityState,
)
from algo_manus.application.risk_controls import LocalRiskControlService
from algo_manus.domain.risk_engine import CentralRiskPolicy
from algo_manus.infrastructure.risk import SqliteRiskControlRepository


class PaperRunEligibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 26, 9, 15, tzinfo=timezone.utc)
        self.policy = PaperRunEligibilityPolicy(
            policy_version="paper-run-evidence-v1",
            max_research_age=timedelta(days=90),
            max_robustness_age=timedelta(days=90),
        )
        self.central_policy = CentralRiskPolicy("paper-run-central-v1", 100, 10_000, 3)

    def _controls(self, root: Path, *, active: bool = False):
        controls = LocalRiskControlService(SqliteRiskControlRepository(root / "risk_controls.sqlite3"))
        controls.save_policy(self.central_policy, now=self.now)
        controls.set_kill_switch(active=active, reason="Option L acceptance fixture", now=self.now)
        return controls.snapshot(self.central_policy.policy_version)

    def _retained_fixture_batch(self, service: FixtureWorkbenchService, *, fast_window: int = 3, slow_window: int = 5):
        return service.run_experiment(
            selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
            fast_window=fast_window,
            slow_window=slow_window,
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
        )

    def test_matching_retained_evidence_is_persisted_and_restart_idempotent_but_not_an_approval(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            workbench = FixtureWorkbenchService(root)
            batch = self._retained_fixture_batch(workbench)
            workbench.run_local_robustness_evaluation(instrument_id="FIXTURE:NSE:EQ:ALPHA")
            evidence = workbench.paper_run_eligibility(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                control_snapshot=self._controls(root),
                policy=self.policy,
                evaluated_at=self.now,
            )
            replayed = FixtureWorkbenchService(root).paper_run_eligibility(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                control_snapshot=self._controls(root),
                policy=self.policy,
                evaluated_at=self.now,
            )

        self.assertEqual(evidence.state, PaperRunEligibilityState.EVIDENCE_COMPLETE)
        self.assertEqual(evidence.blocking_reasons, ())
        self.assertEqual(replayed, evidence)
        self.assertTrue(evidence.robustness_evidence_id.startswith("ROB-"))
        self.assertTrue(evidence.manifest_id.startswith("RUN-"))
        self.assertFalse(hasattr(evidence, "approve"))
        self.assertFalse(hasattr(workbench, "submit"))

    def test_missing_stale_and_kill_switch_evidence_remain_named_blocking_states(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            workbench = FixtureWorkbenchService(root)
            batch = self._retained_fixture_batch(workbench)

            missing = workbench.paper_run_eligibility(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                control_snapshot=self._controls(root),
                policy=self.policy,
                evaluated_at=self.now,
            )
            workbench.run_local_robustness_evaluation(instrument_id="FIXTURE:NSE:EQ:ALPHA")
            stale = workbench.paper_run_eligibility(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                control_snapshot=self._controls(root),
                policy=self.policy,
                evaluated_at=self.now + timedelta(days=100),
            )
            stopped = workbench.paper_run_eligibility(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                control_snapshot=self._controls(root, active=True),
                policy=self.policy,
                evaluated_at=self.now,
            )

        self.assertEqual(missing.state, PaperRunEligibilityState.BLOCKED)
        self.assertIn("ROBUSTNESS_EVIDENCE_MISSING", missing.blocking_reasons)
        self.assertEqual(stale.state, PaperRunEligibilityState.BLOCKED)
        self.assertIn("RESEARCH_EVIDENCE_STALE", stale.blocking_reasons)
        self.assertIn("ROBUSTNESS_EVIDENCE_STALE", stale.blocking_reasons)
        self.assertEqual(stopped.state, PaperRunEligibilityState.BLOCKED)
        self.assertIn("KILL_SWITCH_ACTIVE", stopped.blocking_reasons)

    def test_same_dataset_strategy_but_different_parameter_revision_is_refused(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            workbench = FixtureWorkbenchService(root)
            batch = self._retained_fixture_batch(workbench, fast_window=4, slow_window=6)
            workbench.run_local_robustness_evaluation(instrument_id="FIXTURE:NSE:EQ:ALPHA")

            evidence = workbench.paper_run_eligibility(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                control_snapshot=self._controls(root),
                policy=self.policy,
                evaluated_at=self.now,
            )

        self.assertEqual(evidence.state, PaperRunEligibilityState.BLOCKED)
        self.assertIn("ROBUSTNESS_PARAMETER_REVISION_MISMATCH", evidence.blocking_reasons)

    def test_matching_parameter_revision_with_insufficient_partition_history_is_refused(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            workbench = FixtureWorkbenchService(root)
            batch = self._retained_fixture_batch(workbench, fast_window=3, slow_window=6)
            workbench.run_local_robustness_evaluation(instrument_id="FIXTURE:NSE:EQ:ALPHA")

            evidence = workbench.paper_run_eligibility(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                control_snapshot=self._controls(root),
                policy=self.policy,
                evaluated_at=self.now,
            )

        self.assertEqual(evidence.state, PaperRunEligibilityState.BLOCKED)
        self.assertIn("ROBUSTNESS_HISTORY_INSUFFICIENT", evidence.blocking_reasons)


if __name__ == "__main__":
    unittest.main()
