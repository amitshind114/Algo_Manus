from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.paper_execution import PaperExecutionService
from algo_manus.application.risk_controls import LocalRiskControlService
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, OrderSide, PaperPortfolioSnapshot, RiskLimits
from algo_manus.domain.risk_engine import CentralRiskPolicy, RiskDecisionCode
from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger
from algo_manus.infrastructure.risk import SqliteRiskControlRepository


class RiskControlPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
        self.policy = CentralRiskPolicy("central-persisted-v1", 100, 10_000, 3)

    def test_policy_and_kill_state_survive_restart_and_policy_conflicts_fail(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "risk_controls.sqlite"
            controls = LocalRiskControlService(SqliteRiskControlRepository(path))
            controls.save_policy(self.policy, now=self.now)
            inactive = controls.set_kill_switch(active=False, reason="initialize local paper gate", now=self.now)
            active = controls.set_kill_switch(
                active=True,
                reason="operator stopped local simulation",
                now=datetime(2026, 8, 23, 10, 1, tzinfo=timezone.utc),
            )

            restarted = LocalRiskControlService(SqliteRiskControlRepository(path))
            snapshot = restarted.snapshot(self.policy.policy_version)
            self.assertEqual(snapshot.policy, self.policy)
            self.assertEqual(snapshot.kill_switch_change, active)
            self.assertTrue(snapshot.kill_switch_active)
            self.assertNotEqual(inactive.change_id, active.change_id)
            with self.assertRaisesRegex(ValueError, "conflicts"):
                restarted.save_policy(CentralRiskPolicy("central-persisted-v1", 101, 10_000, 3), now=self.now)

    def test_paper_evidence_uses_persisted_control_snapshot_over_transient_boolean(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory)
            control_service = LocalRiskControlService(SqliteRiskControlRepository(base / "risk_controls.sqlite"))
            control_service.save_policy(self.policy, now=self.now)
            control_service.set_kill_switch(active=True, reason="durable local stop", now=self.now)
            snapshot = control_service.snapshot(self.policy.policy_version)
            ledger = SqlitePaperLedger(base / "paper.sqlite")
            intent = OrderIntent("persisted-control-order", "FIXTURE:NSE:EQ:ALPHA", OrderSide.BUY, 10, 100, "PARAM-risk")
            submission = PaperExecutionService(DeterministicRiskPolicy(), ledger, self.policy).submit(
                intent=intent,
                portfolio=PaperPortfolioSnapshot(1_000, {}, 0, 0),
                marks={intent.instrument_id: 100},
                limits=RiskLimits(2_000, 1_000, 3, 250),
                kill_switch_active=False,
                instrument_status=InstrumentStatus.ACTIVE,
                validation_outcome=DatasetValidationOutcome(
                    dataset_id="DATA-risk",
                    status=DataValidationStatus.ACCEPTED,
                    policy_version="research-dataset-v1",
                    validated_at=self.now,
                ),
                control_snapshot=snapshot,
                now=self.now,
            )

            event_payload = ledger.events_for(intent.order_id)[0].payload
            self.assertFalse(submission.decision.allowed)
            self.assertEqual(submission.central_decision.code, RiskDecisionCode.KILL_SWITCH_ACTIVE)
            self.assertIn(snapshot.kill_switch_change.change_id, event_payload)
            self.assertIn(self.policy.policy_version, event_payload)


if __name__ == "__main__":
    unittest.main()
