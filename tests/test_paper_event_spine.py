"""Option E acceptance tests for local-only, replayable paper operations.

The canonical spine records a simulated proposal and deterministic risk evidence
before an accepted paper lifecycle can progress.  It never calls a broker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from algo_manus.application.paper_execution import PaperExecutionService
from algo_manus.application.paper_projection import PaperOperationsReadService, PaperPortfolioProjector
from algo_manus.domain.execution import ReconciliationDisposition
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.paper import PaperEvent, PaperEventType, PaperOrderStatus
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, OrderSide, PaperPortfolioSnapshot, RiskLimits
from algo_manus.domain.risk_engine import CentralRiskPolicy
from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger


class PaperEventSpineTests(unittest.TestCase):
    """Acceptance coverage for immutable local paper-event behavior only."""

    def setUp(self) -> None:
        self.now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
        self.instrument_id = "FIXTURE:NSE:EQ:SPINE"
        self.intent = OrderIntent("spine-buy", self.instrument_id, OrderSide.BUY, 10, 100, "PARAM-spine")
        self.portfolio = PaperPortfolioSnapshot(2_000, {}, 0, 0)
        self.limits = RiskLimits(5_000, 2_000, 5, 500)
        self.validation = DatasetValidationOutcome(
            dataset_id="DATA-spine",
            status=DataValidationStatus.ACCEPTED,
            policy_version="research-dataset-v1",
            validated_at=self.now,
        )
        self.directory = TemporaryDirectory()
        self.ledger = SqlitePaperLedger(Path(self.directory.name) / "paper.sqlite")
        self.service = PaperExecutionService(
            DeterministicRiskPolicy(),
            self.ledger,
            CentralRiskPolicy("paper-spine-v1", 100, 10_000, 3),
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _submit(self):
        return self.service.submit(
            intent=self.intent,
            portfolio=self.portfolio,
            marks={self.instrument_id: 100},
            limits=self.limits,
            kill_switch_active=False,
            instrument_status=InstrumentStatus.ACTIVE,
            validation_outcome=self.validation,
            now=self.now,
        )

    def test_positive_risk_evidence_precedes_the_accepted_local_lifecycle(self) -> None:
        submission = self._submit()
        events = self.ledger.events_for(self.intent.order_id)

        self.assertTrue(submission.decision.allowed)
        self.assertEqual(submission.order.status, PaperOrderStatus.ACCEPTED)
        self.assertEqual(
            [event.event_type for event in events],
            [
                PaperEventType.ORDER_PROPOSED,
                PaperEventType.RISK_DECISION,
                PaperEventType.ORDER_ACCEPTED,
            ],
        )
        self.assertLess(
            [event.event_type for event in events].index(PaperEventType.RISK_DECISION),
            [event.event_type for event in events].index(PaperEventType.ORDER_ACCEPTED),
        )

    def test_denial_records_no_accepted_working_or_fill_event(self) -> None:
        denied = self.service.submit(
            intent=self.intent,
            portfolio=self.portfolio,
            marks={self.instrument_id: 100},
            limits=self.limits,
            kill_switch_active=True,
            instrument_status=InstrumentStatus.ACTIVE,
            validation_outcome=self.validation,
            now=self.now,
        )
        event_types = {event.event_type for event in self.ledger.events_for(self.intent.order_id)}

        self.assertFalse(denied.decision.allowed)
        self.assertEqual(denied.order.status, PaperOrderStatus.REJECTED)
        self.assertEqual(
            event_types,
            {PaperEventType.ORDER_PROPOSED, PaperEventType.RISK_DECISION, PaperEventType.ORDER_REJECTED},
        )
        with self.assertRaisesRegex(ValueError, "not currently actionable"):
            self.service.fill(denied.order, fill_price=100)

    def test_partial_fills_only_apply_executed_quantity_and_cancel_keeps_remainder_unfilled(self) -> None:
        accepted = self._submit().order
        working = self.service.work(accepted, now=self.now)
        partial = self.service.fill(working, fill_price=100, quantity=4, now=self.now)
        cancelled = self.service.cancel(partial, reason="operator ends local simulation", now=self.now)
        projection = PaperOperationsReadService(self.ledger).portfolio(starting_cash=2_000)

        self.assertEqual(partial.status, PaperOrderStatus.PARTIALLY_FILLED)
        self.assertEqual(partial.filled_quantity, 4)
        self.assertEqual(cancelled.status, PaperOrderStatus.CANCELLED)
        self.assertEqual(projection.cash, 1_600)
        self.assertEqual(projection.realized_pnl, 0)
        self.assertEqual(projection.positions[0].quantity, 4)
        self.assertEqual(projection.orders[0].filled_quantity, 4)
        self.assertEqual(projection.orders[0].remaining_quantity, 6)
        self.assertEqual(projection.orders[0].status, PaperOrderStatus.CANCELLED)
        with self.assertRaisesRegex(ValueError, "not currently actionable"):
            self.service.fill(cancelled, fill_price=100, quantity=1, now=self.now)

    def test_restart_replay_and_reconciliation_evidence_do_not_mutate_projected_cash_or_position(self) -> None:
        accepted = self._submit().order
        filled = self.service.fill(accepted, fill_price=105, now=self.now)
        reconciled = self.service.reconcile(
            filled,
            disposition=ReconciliationDisposition.MATCHED,
            reason="local simulated fill agrees with retained event evidence",
            now=self.now,
        )
        before_restart = PaperOperationsReadService(self.ledger).portfolio(starting_cash=2_000)
        after_restart = PaperOperationsReadService(SqlitePaperLedger(Path(self.directory.name) / "paper.sqlite")).portfolio(
            starting_cash=2_000
        )

        self.assertEqual(reconciled.status, PaperOrderStatus.RECONCILED)
        self.assertEqual(before_restart, after_restart)
        self.assertEqual(after_restart.cash, 950)
        self.assertEqual(after_restart.realized_pnl, 0)
        self.assertEqual(after_restart.positions[0].quantity, 10)
        self.assertEqual(after_restart.orders[0].reconciliation_disposition, ReconciliationDisposition.MATCHED)
        self.assertFalse(after_restart.unprojectable_event_ids)

    def test_replay_marks_missing_risk_duplicate_partial_and_out_of_order_fill_as_unprojectable(self) -> None:
        projector = PaperPortfolioProjector()
        order_id = "manual-order"

        def event(event_id: str, event_type: PaperEventType, payload: dict[str, object]) -> PaperEvent:
            return PaperEvent(
                event_id=event_id,
                event_type=event_type,
                occurred_at=self.now,
                order_id=order_id,
                instrument_id=self.instrument_id,
                payload=json.dumps({"type": event_type.value, "order": order_id, "time": self.now.isoformat(), "payload": payload}),
            )

        result = projector.replay(
            (
                event("accept-without-risk", PaperEventType.ORDER_ACCEPTED, {"side": "BUY", "quantity": 10}),
                event("risk-allow", PaperEventType.RISK_DECISION, {"allowed": True}),
                event("accepted", PaperEventType.ORDER_ACCEPTED, {"side": "BUY", "quantity": 10}),
                event("working", PaperEventType.ORDER_WORKING, {"side": "BUY", "quantity": 10}),
                event(
                    "partial-four",
                    PaperEventType.ORDER_PARTIALLY_FILLED,
                    {"side": "BUY", "quantity": 4, "fill_price": 100, "cumulative_filled_quantity": 4},
                ),
                event(
                    "duplicate-partial",
                    PaperEventType.ORDER_PARTIALLY_FILLED,
                    {"side": "BUY", "quantity": 4, "fill_price": 100, "cumulative_filled_quantity": 4},
                ),
                event(
                    "complete-six",
                    PaperEventType.ORDER_FILLED,
                    {"side": "BUY", "quantity": 6, "fill_price": 110, "cumulative_filled_quantity": 10},
                ),
                event(
                    "duplicate-fill",
                    PaperEventType.ORDER_FILLED,
                    {"side": "BUY", "quantity": 6, "fill_price": 110, "cumulative_filled_quantity": 10},
                ),
            ),
            starting_cash=2_000,
        )

        self.assertEqual(result.cash, 940)
        self.assertEqual(result.positions[0].quantity, 10)
        self.assertEqual(result.positions[0].average_entry_price, 106)
        self.assertEqual(
            result.unprojectable_event_ids,
            ("accept-without-risk", "duplicate-partial", "duplicate-fill"),
        )


if __name__ == "__main__":
    unittest.main()
