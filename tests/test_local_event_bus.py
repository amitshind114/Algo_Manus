"""Option G acceptance tests for the bounded local in-process event bus.

The bus is deliberately process-local and non-durable.  Its events point to
already-retained research or paper evidence; it never calls a broker, a network
service, an external queue, or a background worker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService
from algo_manus.application.local_event_audit import LocalEventWiringAuditReadService
from algo_manus.application.local_event_bus import (
    LocalApplicationEvent,
    LocalEventBus,
    LocalEventDeliveryStatus,
    LocalEventType,
)
from algo_manus.application.paper_execution import PaperExecutionService
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, OrderSide, PaperPortfolioSnapshot, RiskLimits
from algo_manus.domain.risk_engine import CentralRiskPolicy
from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger


class LocalEventBusTests(unittest.TestCase):
    """Verify local event wiring without external event infrastructure."""

    def setUp(self) -> None:
        self.now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)

    def test_immutable_event_is_dispatched_in_order_once_and_duplicate_suppression_is_safe(self) -> None:
        bus = LocalEventBus(max_events=10)
        observed: list[LocalApplicationEvent] = []
        bus.subscribe("capture", observed.append)
        event = LocalApplicationEvent.create(
            event_type=LocalEventType.RESEARCH_BATCH_RETAINED,
            occurred_at=self.now,
            correlation_id="EXP-local",
            producer="test",
            attributes={"batch_id": "EXP-local", "source_evidence_id": "EXP-local"},
        )

        first = bus.publish(event)
        duplicate = bus.publish(event)

        self.assertTrue(first.accepted)
        self.assertFalse(duplicate.accepted)
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(bus.events(), (event,))
        self.assertEqual(observed, [event])
        deliveries = bus.deliveries(event_id=event.event_id)
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].status, LocalEventDeliveryStatus.DELIVERED)

    def test_subscriber_failure_is_audited_and_does_not_block_other_local_subscribers(self) -> None:
        bus = LocalEventBus(max_events=10)
        observed: list[str] = []

        def broken(_: LocalApplicationEvent) -> None:
            raise RuntimeError("intentional local test failure")

        bus.subscribe("broken", broken)
        bus.subscribe("healthy", lambda item: observed.append(item.event_id))
        event = LocalApplicationEvent.create(
            event_type=LocalEventType.PAPER_LEDGER_EVENT_RETAINED,
            occurred_at=self.now,
            correlation_id="paper-local",
            producer="test",
            attributes={"source_evidence_id": "PE-local", "paper_event_type": "ORDER_PROPOSED"},
        )

        result = bus.publish(event)
        deliveries = bus.deliveries(event_id=event.event_id)

        self.assertTrue(result.accepted)
        self.assertEqual(observed, [event.event_id])
        self.assertEqual([item.subscriber_name for item in deliveries], ["broken", "healthy"])
        self.assertEqual([item.status for item in deliveries], [LocalEventDeliveryStatus.FAILED, LocalEventDeliveryStatus.DELIVERED])
        self.assertEqual(deliveries[0].failure_type, "RuntimeError")
        audit = LocalEventWiringAuditReadService(bus)
        audit_row = audit.rows()[0]
        self.assertEqual(audit_row.event_id, event.event_id)
        self.assertEqual(audit_row.source_evidence_id, "PE-local")
        self.assertEqual(audit_row.delivered_subscriber_count, 1)
        self.assertEqual(audit_row.failed_subscriber_count, 1)
        self.assertFalse(audit.snapshot().is_durable)

    def test_research_and_risk_first_paper_events_publish_only_after_their_source_evidence_is_retained(self) -> None:
        bus = LocalEventBus(max_events=100)
        workbench = FixtureWorkbenchService(event_bus=bus)
        batch = workbench.run_experiment(
            selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
            fast_window=2,
            slow_window=4,
            initial_cash=10_000,
            quantity=10,
            commission_bps=0,
            slippage_bps=0,
        )
        with TemporaryDirectory() as directory:
            ledger = SqlitePaperLedger(Path(directory) / "paper.sqlite")
            service = PaperExecutionService(
                DeterministicRiskPolicy(),
                ledger,
                CentralRiskPolicy("event-bus-paper-v1", 100, 10_000, 3),
                event_bus=bus,
            )
            instrument_id = "FIXTURE:NSE:EQ:ALPHA"
            submission = service.submit(
                intent=OrderIntent("event-paper", instrument_id, OrderSide.BUY, 10, 100, "PARAM-event"),
                portfolio=PaperPortfolioSnapshot(2_000, {}, 0, 0),
                marks={instrument_id: 100},
                limits=RiskLimits(5_000, 2_000, 5, 500),
                kill_switch_active=False,
                instrument_status=InstrumentStatus.ACTIVE,
                validation_outcome=DatasetValidationOutcome(
                    dataset_id="DATA-event",
                    status=DataValidationStatus.ACCEPTED,
                    policy_version="research-dataset-v1",
                    validated_at=self.now,
                ),
                now=self.now,
            )

            self.assertTrue(submission.decision.allowed)
            self.assertEqual(len(ledger.events_for("event-paper")), 3)
            events = bus.events()
            self.assertEqual(events[0].event_type, LocalEventType.RESEARCH_BATCH_RETAINED)
            self.assertEqual(events[0].correlation_id, batch.batch_id)
            paper_events = [item for item in events if item.event_type is LocalEventType.PAPER_LEDGER_EVENT_RETAINED]
            self.assertEqual([item.attributes["paper_event_type"] for item in paper_events], ["ORDER_PROPOSED", "RISK_DECISION", "ORDER_ACCEPTED"])
            self.assertEqual([item.attributes["source_evidence_id"] for item in paper_events], [item.event_id for item in ledger.events_for("event-paper")])

    def test_bus_audit_is_bounded_process_local_and_does_not_replay_after_restart(self) -> None:
        bus = LocalEventBus(max_events=1)
        event = LocalApplicationEvent.create(
            event_type=LocalEventType.RESEARCH_BATCH_RETAINED,
            occurred_at=self.now,
            correlation_id="EXP-boundary",
            producer="test",
            attributes={"batch_id": "EXP-boundary", "source_evidence_id": "EXP-boundary"},
        )
        bus.publish(event)

        restarted_bus = LocalEventBus(max_events=1)

        self.assertEqual(bus.events(), (event,))
        self.assertFalse(bus.is_durable)
        self.assertEqual(restarted_bus.events(), ())
        self.assertEqual(restarted_bus.deliveries(), ())


if __name__ == "__main__":
    unittest.main()
