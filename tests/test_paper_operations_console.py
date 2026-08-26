"""Option H acceptance tests for the event-derived local paper operations console."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.local_event_bus import LocalEventBus
from algo_manus.application.paper_execution import PaperExecutionService
from algo_manus.application.paper_operations_console import LocalPaperOperationsConsoleReadService
from algo_manus.domain.execution import ReconciliationDisposition
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.paper import LocalLimitFillAssumptions, LocalOrderType, PaperEvent, PaperEventType
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, OrderSide, PaperPortfolioSnapshot, RiskLimits
from algo_manus.domain.risk_engine import CentralRiskPolicy
from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger


class LocalPaperOperationsConsoleTests(unittest.TestCase):
    """Verify the console only consolidates retained evidence and local diagnostics."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.ledger = SqlitePaperLedger(Path(self.directory.name) / "paper.sqlite")
        self.bus = LocalEventBus()
        self.now = datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc)
        self.execution = PaperExecutionService(
            DeterministicRiskPolicy(),
            self.ledger,
            CentralRiskPolicy("console-v1", 100, 100_000, 5),
            event_bus=self.bus,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_console_aggregates_risk_lifecycle_simulator_reconciliation_and_wiring_from_retained_evidence(self) -> None:
        intent = OrderIntent("console-order", "FIXTURE:NSE:EQ:ALPHA", OrderSide.BUY, 10, 100, "PARAM-console")
        submission = self.execution.submit(
            intent=intent,
            portfolio=PaperPortfolioSnapshot(10_000, {}, 0, 0),
            marks={intent.instrument_id: 100},
            limits=RiskLimits(50_000, 50_000, 5, 1_000),
            kill_switch_active=False,
            instrument_status=InstrumentStatus.ACTIVE,
            validation_outcome=DatasetValidationOutcome(
                dataset_id="DATA-console",
                status=DataValidationStatus.ACCEPTED,
                policy_version="research-dataset-v1",
                validated_at=self.now,
            ),
            now=self.now,
        )
        working = self.execution.work(submission.order, now=self.now)
        self.execution.simulate_limit_fill(
            working,
            assumptions=LocalLimitFillAssumptions(
                LocalOrderType.LIMIT, 100, 101, 10, 0, True, "local-limit-fill-v1"
            ),
            now=self.now,
        )
        partial = self.execution.simulate_limit_fill(
            working,
            assumptions=LocalLimitFillAssumptions(
                LocalOrderType.LIMIT, 100, 100, 4, 0, True, "local-limit-fill-v1"
            ),
            now=self.now,
        )
        filled = self.execution.simulate_limit_fill(
            partial.order,
            assumptions=LocalLimitFillAssumptions(
                LocalOrderType.LIMIT, 100, 100, 6, 0, True, "local-limit-fill-v1"
            ),
            now=self.now,
        )
        self.execution.reconcile(
            filled.order,
            disposition=ReconciliationDisposition.MATCHED,
            reason="local scenario evidence reviewed",
            now=self.now,
        )

        snapshot = LocalPaperOperationsConsoleReadService(self.ledger, self.bus).snapshot(starting_cash=10_000)

        self.assertEqual(snapshot.projection.cash, 9_000)
        self.assertEqual(snapshot.projection.positions[0].quantity, 10)
        self.assertEqual(snapshot.lifecycle_counts["RECONCILED"], 1)
        self.assertEqual(snapshot.simulator_outcome_counts["NO_FILL"], 1)
        self.assertEqual(snapshot.simulator_outcome_counts["PARTIAL_FILL"], 1)
        self.assertEqual(snapshot.simulator_outcome_counts["FILLED"], 1)
        self.assertEqual(snapshot.reconciliation_counts["MATCHED"], 1)
        self.assertTrue(snapshot.latest_risk_decision.allowed)
        self.assertEqual(snapshot.latest_risk_decision.central_decision_type, "ALLOW")
        self.assertEqual(snapshot.integrity.total_events, 8)
        self.assertEqual(snapshot.wiring.retained_event_count, 8)
        self.assertFalse(snapshot.wiring.is_durable)
        self.assertEqual(snapshot.wiring.failed_delivery_count, 0)

    def test_empty_console_is_safe_and_exposes_no_actionable_operation(self) -> None:
        console = LocalPaperOperationsConsoleReadService(self.ledger, self.bus)

        snapshot = console.snapshot(starting_cash=10_000)

        self.assertEqual(snapshot.projection.orders, ())
        self.assertEqual(snapshot.integrity.total_events, 0)
        self.assertEqual(dict(snapshot.lifecycle_counts), {})
        self.assertIsNone(snapshot.latest_risk_decision)
        self.assertEqual(snapshot.wiring.retained_event_count, 0)
        self.assertFalse(hasattr(console, "submit"))
        self.assertFalse(hasattr(console, "publish"))
        self.assertFalse(hasattr(console, "reconcile"))

    def test_malformed_retained_event_is_isolated_in_console_integrity_and_replay_diagnostics(self) -> None:
        self.ledger.append(
            PaperEvent(
                event_id="PE-console-malformed",
                event_type=PaperEventType.ORDER_FILLED,
                occurred_at=self.now,
                order_id="console-malformed",
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                payload="{not-json",
            )
        )

        snapshot = LocalPaperOperationsConsoleReadService(self.ledger, self.bus).snapshot(starting_cash=10_000)

        self.assertEqual(snapshot.integrity.total_events, 1)
        self.assertEqual(snapshot.integrity.malformed_payload_events, 1)
        self.assertEqual(snapshot.projection.cash, 10_000)
        self.assertEqual(snapshot.projection.unprojectable_event_ids, ("PE-console-malformed",))


if __name__ == "__main__":
    unittest.main()
