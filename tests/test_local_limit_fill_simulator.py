"""Option F acceptance tests for the conservative local paper limit-fill simulator.

Every scenario uses explicit caller-supplied simulation inputs.  No test relies on
or implies broker prices, order-book data, venue acknowledgements, or live orders.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.paper_execution import PaperExecutionService
from algo_manus.application.paper_audit import PaperOperationAuditTimelineReadService
from algo_manus.application.paper_projection import PaperOperationsReadService
from algo_manus.domain.execution import ReconciliationDisposition
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.paper import (
    LocalLimitFillAssumptions,
    LocalOrderType,
    PaperEventType,
    PaperFillSimulationOutcome,
    PaperOrderStatus,
)
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, OrderSide, PaperPortfolioSnapshot, RiskLimits
from algo_manus.domain.risk_engine import CentralRiskPolicy
from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger


class LocalLimitFillSimulatorTests(unittest.TestCase):
    """Acceptance coverage for explicit, conservative local fill assumptions only."""

    def setUp(self) -> None:
        self.now = datetime(2026, 8, 26, 11, 0, tzinfo=timezone.utc)
        self.instrument_id = "FIXTURE:NSE:EQ:LIMIT"
        self.intent = OrderIntent("limit-buy", self.instrument_id, OrderSide.BUY, 10, 100, "PARAM-limit")
        self.portfolio = PaperPortfolioSnapshot(2_000, {}, 0, 0)
        self.limits = RiskLimits(5_000, 2_000, 5, 500)
        self.validation = DatasetValidationOutcome(
            dataset_id="DATA-limit",
            status=DataValidationStatus.ACCEPTED,
            policy_version="research-dataset-v1",
            validated_at=self.now,
        )
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name) / "paper.sqlite"
        self.ledger = SqlitePaperLedger(self.path)
        self.service = PaperExecutionService(
            DeterministicRiskPolicy(),
            self.ledger,
            CentralRiskPolicy("paper-limit-v1", 100, 10_000, 3),
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _accepted(self, order_id: str = "limit-buy"):
        intent = OrderIntent(order_id, self.instrument_id, OrderSide.BUY, 10, 100, "PARAM-limit")
        return self.service.submit(
            intent=intent,
            portfolio=self.portfolio,
            marks={self.instrument_id: 100},
            limits=self.limits,
            kill_switch_active=False,
            instrument_status=InstrumentStatus.ACTIVE,
            validation_outcome=self.validation,
            now=self.now,
        ).order

    @staticmethod
    def _assumptions(
        *,
        limit_price: float,
        observed_price: float = 100,
        available_quantity: int = 10,
        adverse_slippage_bps: float = 0,
        session_open: bool = True,
        order_type: LocalOrderType = LocalOrderType.LIMIT,
    ) -> LocalLimitFillAssumptions:
        return LocalLimitFillAssumptions(
            order_type=order_type,
            limit_price=limit_price,
            observed_price=observed_price,
            available_quantity=available_quantity,
            adverse_slippage_bps=adverse_slippage_bps,
            session_open=session_open,
            model_version="local-limit-fill-v1",
        )

    def test_market_order_assumption_is_rejected_without_new_paper_event(self) -> None:
        accepted = self._accepted()
        event_count_before = len(self.ledger.events_for(accepted.intent.order_id))

        with self.assertRaisesRegex(ValueError, "limit order"):
            self.service.simulate_limit_fill(
                accepted,
                assumptions=self._assumptions(limit_price=100, order_type=LocalOrderType.MARKET),
                now=self.now,
            )

        self.assertEqual(len(self.ledger.events_for(accepted.intent.order_id)), event_count_before)

    def test_no_fill_then_volume_capped_partial_and_final_fill_replay_from_explicit_local_inputs(self) -> None:
        working = self.service.work(self._accepted(), now=self.now)
        no_fill = self.service.simulate_limit_fill(
            working,
            assumptions=self._assumptions(limit_price=99, observed_price=100, available_quantity=10),
            now=self.now,
        )
        partial = self.service.simulate_limit_fill(
            no_fill.order,
            assumptions=self._assumptions(
                limit_price=100.6,
                observed_price=100,
                available_quantity=4,
                adverse_slippage_bps=50,
            ),
            now=self.now,
        )
        filled = self.service.simulate_limit_fill(
            partial.order,
            assumptions=self._assumptions(limit_price=101, observed_price=100, available_quantity=10),
            now=self.now,
        )
        projection = PaperOperationsReadService(self.ledger).portfolio(starting_cash=2_000)
        event_types = [event.event_type for event in self.ledger.events_for(working.intent.order_id)]

        self.assertEqual(no_fill.outcome, PaperFillSimulationOutcome.NO_FILL)
        self.assertEqual(no_fill.order.status, PaperOrderStatus.WORKING)
        self.assertEqual(partial.outcome, PaperFillSimulationOutcome.PARTIAL_FILL)
        self.assertEqual(partial.order.filled_quantity, 4)
        self.assertEqual(partial.order.fill_price, 100.5)
        self.assertEqual(filled.outcome, PaperFillSimulationOutcome.FILLED)
        self.assertEqual(filled.order.status, PaperOrderStatus.FILLED)
        self.assertEqual(event_types.count(PaperEventType.ORDER_UNFILLED), 1)
        self.assertEqual(event_types.count(PaperEventType.ORDER_PARTIALLY_FILLED), 1)
        self.assertEqual(event_types.count(PaperEventType.ORDER_FILLED), 1)
        self.assertEqual(projection.cash, 2_000 - (4 * 100.5) - (6 * 100))
        self.assertEqual(projection.positions[0].quantity, 10)
        self.assertEqual(projection.positions[0].average_entry_price, ((4 * 100.5) + (6 * 100)) / 10)
        self.assertFalse(projection.unprojectable_event_ids)
        audit_rows = PaperOperationAuditTimelineReadService(self.ledger).rows(
            order_id=working.intent.order_id,
            event_type_filter="ORDER_UNFILLED",
        )
        self.assertEqual(len(audit_rows), 1)
        self.assertEqual(audit_rows[0].simulation_outcome, "NO_FILL")
        self.assertEqual(audit_rows[0].simulation_reason_code, "LIMIT_NOT_ELIGIBLE")
        self.assertEqual(audit_rows[0].simulation_model_version, "local-limit-fill-v1")

    def test_closed_session_no_fill_cancel_duplicate_request_restart_replay_and_reconciliation_are_safe(self) -> None:
        accepted = self._accepted()
        working = self.service.work(accepted, now=self.now)
        no_fill = self.service.simulate_limit_fill(
            working,
            assumptions=self._assumptions(limit_price=101, session_open=False),
            now=self.now,
        )
        cancelled = self.service.cancel(no_fill.order, reason="local simulation window closed", now=self.now)
        reconciled = self.service.reconcile(
            cancelled,
            disposition=ReconciliationDisposition.UNRESOLVED,
            reason="no external venue report exists in this local-only scenario",
            now=self.now,
        )
        duplicate = self._accepted(order_id=accepted.intent.order_id)
        before_restart = PaperOperationsReadService(self.ledger).portfolio(starting_cash=2_000)
        after_restart = PaperOperationsReadService(SqlitePaperLedger(self.path)).portfolio(starting_cash=2_000)

        self.assertEqual(no_fill.outcome, PaperFillSimulationOutcome.NO_FILL)
        self.assertEqual(no_fill.reason_code, "SESSION_CLOSED")
        self.assertEqual(cancelled.status, PaperOrderStatus.CANCELLED)
        self.assertEqual(reconciled.status, PaperOrderStatus.RECONCILED)
        self.assertFalse(duplicate.status is PaperOrderStatus.ACCEPTED)
        self.assertEqual(before_restart, after_restart)
        self.assertEqual(after_restart.cash, 2_000)
        self.assertFalse(after_restart.positions)
        self.assertEqual(after_restart.orders[0].reconciliation_disposition, ReconciliationDisposition.UNRESOLVED)


if __name__ == "__main__":
    unittest.main()
