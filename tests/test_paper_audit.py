from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from algo_manus.application.paper_execution import PaperExecutionService
from algo_manus.application.paper_audit import PaperOperationAuditTimelineReadService
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.paper import PaperEvent, PaperEventType, PaperPromotionEvidence
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import (
    DeterministicRiskPolicy,
    OrderIntent,
    OrderSide,
    PaperPortfolioSnapshot,
    RiskLimits,
)
from algo_manus.domain.risk_engine import CentralRiskPolicy
from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger


class PaperOperationAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "paper.sqlite3"
        self.ledger = SqlitePaperLedger(self.path)
        self.service = PaperExecutionService(
            DeterministicRiskPolicy(),
            self.ledger,
            CentralRiskPolicy("central-audit-v1", 100, 10_000, 10),
            require_promotion_evidence=True,
        )
        self.now = datetime(2026, 8, 23, 9, 30, tzinfo=timezone.utc)
        self.validation = DatasetValidationOutcome(
            dataset_id="DATA-paper-audit",
            status=DataValidationStatus.ACCEPTED,
            policy_version="research-dataset-v1",
            validated_at=self.now,
        )
        self.portfolio = PaperPortfolioSnapshot(cash=100_000, positions={}, realized_pnl=0, session_order_count=0)
        self.limits = RiskLimits(200_000, 100_000, 10, 10_000)
        self.evidence = PaperPromotionEvidence(
            batch_id="EXP-audit",
            manifest_id="RUN-audit",
            dataset_id=self.validation.dataset_id,
            validation_policy_version=self.validation.policy_version,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _intent(self, order_id: str) -> OrderIntent:
        return OrderIntent(
            order_id=order_id,
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            side=OrderSide.BUY,
            quantity=5,
            reference_price=100,
            strategy_revision_id="PARAM-audit",
        )

    def _submit(self, *, order_id: str, kill_switch_active: bool = False):
        return self.service.submit(
            intent=self._intent(order_id),
            portfolio=self.portfolio,
            marks={"FIXTURE:NSE:EQ:ALPHA": 100},
            limits=self.limits,
            kill_switch_active=kill_switch_active,
            instrument_status=InstrumentStatus.ACTIVE,
            validation_outcome=self.validation,
            promotion_evidence=self.evidence,
            now=self.now,
        )

    def test_empty_ledger_has_no_audit_rows(self) -> None:
        self.assertEqual(PaperOperationAuditTimelineReadService(self.ledger).rows(), ())

    def test_restart_safe_timeline_exposes_lifecycle_and_promotion_context(self) -> None:
        filled_submission = self._submit(order_id="paper-audit-filled")
        self.service.fill(filled_submission.order, fill_price=101, now=self.now + timedelta(minutes=1))
        cancelled_submission = self._submit(order_id="paper-audit-cancelled")
        self.service.cancel(cancelled_submission.order, reason="fixture cancel", now=self.now + timedelta(minutes=2))
        self._submit(order_id="paper-audit-rejected", kill_switch_active=True)

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        rows = restarted.rows()
        by_order = {row.order_id: [item for item in rows if item.order_id == row.order_id] for row in rows}

        self.assertEqual([row.lifecycle_state for row in by_order["paper-audit-filled"]], ["PENDING_RISK", "SUBMITTED", "FILLED"])
        self.assertEqual([row.lifecycle_state for row in by_order["paper-audit-cancelled"]], ["PENDING_RISK", "SUBMITTED", "CANCELLED"])
        self.assertEqual([row.lifecycle_state for row in by_order["paper-audit-rejected"]], ["PENDING_RISK", "REJECTED"])
        risk_row = by_order["paper-audit-filled"][0]
        self.assertEqual(risk_row.research_batch_id, "EXP-audit")
        self.assertEqual(risk_row.research_manifest_id, "RUN-audit")
        self.assertEqual(by_order["paper-audit-filled"][1].quantity, 5)
        self.assertEqual(by_order["paper-audit-filled"][-1].fill_price, 101.0)

    def test_malformed_payload_and_invalid_sequence_remain_visible_without_invention(self) -> None:
        self.ledger.append(
            PaperEvent(
                event_id="EVT-audit-malformed",
                event_type=PaperEventType.ORDER_FILLED,
                occurred_at=self.now,
                order_id="paper-audit-malformed",
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                payload="not-json",
            )
        )

        row = PaperOperationAuditTimelineReadService(self.ledger).rows()[0]

        self.assertFalse(row.payload_valid)
        self.assertEqual(row.lifecycle_state, "UNPROJECTABLE")
        self.assertIsNone(row.side)
        self.assertIsNone(row.quantity)
        self.assertIsNone(row.reference_price)

    def test_order_filter_returns_only_requested_retained_order_after_restart(self) -> None:
        first = self._submit(order_id="paper-audit-first")
        self.service.fill(first.order, fill_price=101, now=self.now + timedelta(minutes=1))
        second = self._submit(order_id="paper-audit-second")
        self.service.cancel(second.order, reason="fixture cancel", now=self.now + timedelta(minutes=2))

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        filtered = restarted.rows(order_id="paper-audit-second")

        self.assertEqual([row.order_id for row in filtered], ["paper-audit-second"] * 3)
        self.assertEqual([row.lifecycle_state for row in filtered], ["PENDING_RISK", "SUBMITTED", "CANCELLED"])

    def test_order_filter_rejects_blank_or_unknown_order_identifiers(self) -> None:
        self._submit(order_id="paper-audit-known")
        audit = PaperOperationAuditTimelineReadService(self.ledger)

        with self.assertRaisesRegex(ValueError, "order_id"):
            audit.rows(order_id=" ")
        with self.assertRaisesRegex(ValueError, "unknown"):
            audit.rows(order_id="paper-audit-unknown")

    def test_integrity_statuses_and_totals_survive_restart_without_repair(self) -> None:
        self._submit(order_id="paper-audit-integrity-valid")
        self.ledger.append(
            PaperEvent(
                event_id="EVT-audit-payload-invalid",
                event_type=PaperEventType.RISK_DECISION,
                occurred_at=self.now + timedelta(minutes=1),
                order_id="paper-audit-payload-invalid",
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                payload="not-json",
            )
        )
        self.ledger.append(
            PaperEvent(
                event_id="EVT-audit-lifecycle-invalid",
                event_type=PaperEventType.ORDER_FILLED,
                occurred_at=self.now + timedelta(minutes=2),
                order_id="paper-audit-lifecycle-invalid",
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                payload=json.dumps({"payload": {"fill_price": 101}}),
            )
        )
        self.ledger.append(
            PaperEvent(
                event_id="EVT-audit-both-invalid",
                event_type=PaperEventType.ORDER_CANCELLED,
                occurred_at=self.now + timedelta(minutes=3),
                order_id="paper-audit-both-invalid",
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                payload="not-json",
            )
        )

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        rows = {row.event_id: row for row in restarted.rows()}
        summary = restarted.integrity()

        self.assertEqual(rows["EVT-audit-payload-invalid"].integrity_status, "MALFORMED_PAYLOAD")
        self.assertEqual(rows["EVT-audit-lifecycle-invalid"].integrity_status, "INVALID_LIFECYCLE")
        self.assertEqual(
            rows["EVT-audit-both-invalid"].integrity_status,
            "MALFORMED_PAYLOAD_AND_INVALID_LIFECYCLE",
        )
        self.assertEqual(summary.total_events, 5)
        self.assertEqual(summary.valid_events, 2)
        self.assertEqual(summary.malformed_payload_events, 2)
        self.assertEqual(summary.invalid_lifecycle_events, 2)

    def test_integrity_filter_scopes_rows_and_totals_after_restart(self) -> None:
        self._submit(order_id="paper-audit-filter-valid")
        self.ledger.append(
            PaperEvent(
                event_id="EVT-audit-filter-payload-invalid",
                event_type=PaperEventType.RISK_DECISION,
                occurred_at=self.now + timedelta(minutes=1),
                order_id="paper-audit-filter-payload-invalid",
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                payload="not-json",
            )
        )
        self.ledger.append(
            PaperEvent(
                event_id="EVT-audit-filter-lifecycle-invalid",
                event_type=PaperEventType.ORDER_FILLED,
                occurred_at=self.now + timedelta(minutes=2),
                order_id="paper-audit-filter-lifecycle-invalid",
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                payload=json.dumps({"payload": {"fill_price": 101}}),
            )
        )

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        all_rows = restarted.rows(integrity_filter="ALL")
        valid_rows = restarted.rows(integrity_filter="VALID")
        issue_rows = restarted.rows(integrity_filter="ISSUES")
        issue_summary = restarted.integrity(integrity_filter="ISSUES")

        self.assertEqual(len(all_rows), 4)
        self.assertEqual([row.integrity_status for row in valid_rows], ["VALID", "VALID"])
        self.assertEqual(
            {row.integrity_status for row in issue_rows},
            {"MALFORMED_PAYLOAD", "INVALID_LIFECYCLE"},
        )
        self.assertEqual(issue_summary.total_events, 2)
        self.assertEqual(issue_summary.valid_events, 0)

    def test_integrity_filter_rejects_blank_or_unknown_values(self) -> None:
        audit = PaperOperationAuditTimelineReadService(self.ledger)

        with self.assertRaisesRegex(ValueError, "integrity_filter"):
            audit.rows(integrity_filter=" ")
        with self.assertRaisesRegex(ValueError, "unknown"):
            audit.rows(integrity_filter="incomplete")


if __name__ == "__main__":
    unittest.main()
