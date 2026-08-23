from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from algo_manus.application.paper_execution import PaperExecutionService
from algo_manus.domain.paper import PaperEventType, PaperOrderStatus
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import (
    DeterministicRiskPolicy,
    OrderIntent,
    OrderSide,
    PaperPortfolioSnapshot,
    RiskLimits,
)
from algo_manus.domain.risk_engine import CentralRiskPolicy, RiskDecisionCode, RiskDecisionType
from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger


class PaperExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger = SqlitePaperLedger(Path(self.temp_dir.name) / "paper.sqlite3")
        self.service = PaperExecutionService(
            DeterministicRiskPolicy(),
            self.ledger,
            CentralRiskPolicy("central-paper-v1", 100, 1_000, 3),
        )
        self.intent = OrderIntent(
            order_id="paper-order-1",
            instrument_id="ANGEL_ONE:NSE:NSE:500325",
            side=OrderSide.BUY,
            quantity=5,
            reference_price=100,
            strategy_revision_id="PARAM-fixture",
        )
        self.portfolio = PaperPortfolioSnapshot(
            cash=1_000,
            positions={},
            realized_pnl=0,
            session_order_count=0,
        )
        self.limits = RiskLimits(
            max_gross_notional=2_000,
            max_notional_per_instrument=1_000,
            max_session_orders=3,
            max_daily_loss=250,
        )
        self.now = datetime(2026, 8, 23, 9, 30, tzinfo=timezone.utc)
        self.validation = DatasetValidationOutcome(
            dataset_id="DATA-paper-fixture",
            status=DataValidationStatus.ACCEPTED,
            policy_version="research-dataset-v1",
            validated_at=self.now,
        )

    def _central_context(self) -> dict:
        return {
            "instrument_status": InstrumentStatus.ACTIVE,
            "validation_outcome": self.validation,
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_approved_paper_order_records_decision_submission_and_fill(self) -> None:
        submission = self.service.submit(
            intent=self.intent,
            portfolio=self.portfolio,
            marks={self.intent.instrument_id: 100},
            limits=self.limits,
            kill_switch_active=False,
            **self._central_context(),
            now=self.now,
        )
        filled = self.service.fill(submission.order, fill_price=101, now=self.now)
        events = self.ledger.events_for(self.intent.order_id)

        self.assertTrue(submission.decision.allowed)
        self.assertEqual(submission.central_decision.decision_type, RiskDecisionType.ALLOW)
        self.assertEqual(submission.central_decision.code, RiskDecisionCode.APPROVED)
        self.assertEqual(submission.order.status, PaperOrderStatus.SUBMITTED)
        self.assertEqual(filled.status, PaperOrderStatus.FILLED)
        self.assertEqual(
            [event.event_type for event in events],
            [PaperEventType.RISK_DECISION, PaperEventType.ORDER_SUBMITTED, PaperEventType.ORDER_FILLED],
        )

    def test_kill_switch_rejects_before_submission(self) -> None:
        submission = self.service.submit(
            intent=self.intent,
            portfolio=self.portfolio,
            marks={self.intent.instrument_id: 100},
            limits=self.limits,
            kill_switch_active=True,
            **self._central_context(),
            now=self.now,
        )
        events = self.ledger.events_for(self.intent.order_id)

        self.assertFalse(submission.decision.allowed)
        self.assertEqual(submission.decision.code, "CENTRAL_REJECT_KILL_SWITCH_ACTIVE")
        self.assertEqual(submission.order.status, PaperOrderStatus.REJECTED)
        self.assertEqual(
            [event.event_type for event in events],
            [PaperEventType.RISK_DECISION, PaperEventType.ORDER_REJECTED],
        )

    def test_missing_context_defers_before_legacy_paper_submission(self) -> None:
        submission = self.service.submit(
            intent=self.intent,
            portfolio=self.portfolio,
            marks={self.intent.instrument_id: 100},
            limits=self.limits,
            kill_switch_active=False,
            instrument_status=None,
            validation_outcome=self.validation,
            now=self.now,
        )

        self.assertFalse(submission.decision.allowed)
        self.assertEqual(submission.central_decision.decision_type, RiskDecisionType.DEFER)
        self.assertEqual(submission.central_decision.code, RiskDecisionCode.INSTRUMENT_CONTEXT_MISSING)
        self.assertEqual(submission.order.status, PaperOrderStatus.REJECTED)
        self.assertEqual(
            [event.event_type for event in self.ledger.events_for(self.intent.order_id)],
            [PaperEventType.RISK_DECISION, PaperEventType.ORDER_REJECTED],
        )

    def test_existing_ledger_order_identity_rejects_duplicate_submission(self) -> None:
        first = self.service.submit(
            intent=self.intent,
            portfolio=self.portfolio,
            marks={self.intent.instrument_id: 100},
            limits=self.limits,
            kill_switch_active=False,
            **self._central_context(),
            now=self.now,
        )
        duplicate = self.service.submit(
            intent=self.intent,
            portfolio=self.portfolio,
            marks={self.intent.instrument_id: 100},
            limits=self.limits,
            kill_switch_active=False,
            **self._central_context(),
            now=self.now,
        )

        self.assertTrue(first.decision.allowed)
        self.assertFalse(duplicate.decision.allowed)
        self.assertEqual(duplicate.central_decision.code, RiskDecisionCode.DUPLICATE_INTENT)
        self.assertEqual(duplicate.order.status, PaperOrderStatus.REJECTED)


if __name__ == "__main__":
    unittest.main()
