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

    def _intent(self, order_id: str, side: OrderSide = OrderSide.BUY) -> OrderIntent:
        return OrderIntent(
            order_id=order_id,
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            side=side,
            quantity=5,
            reference_price=100,
            strategy_revision_id="PARAM-audit",
        )

    def _submit(
        self,
        *,
        order_id: str,
        side: OrderSide = OrderSide.BUY,
        kill_switch_active: bool = False,
    ):
        return self.service.submit(
            intent=self._intent(order_id, side),
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

    def test_event_type_filter_scopes_rows_and_totals_after_restart(self) -> None:
        submission = self._submit(order_id="paper-audit-event-filter")
        self.service.fill(submission.order, fill_price=101, now=self.now + timedelta(minutes=1))

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        all_rows = restarted.rows(event_type_filter="ALL")
        fill_rows = restarted.rows(event_type_filter="ORDER_FILLED")
        fill_summary = restarted.integrity(event_type_filter="ORDER_FILLED")

        self.assertEqual([row.event_type for row in all_rows], ["RISK_DECISION", "ORDER_SUBMITTED", "ORDER_FILLED"])
        self.assertEqual([row.event_type for row in fill_rows], ["ORDER_FILLED"])
        self.assertEqual(fill_summary.total_events, 1)
        self.assertEqual(fill_summary.valid_events, 1)

    def test_event_type_filter_rejects_blank_or_unknown_values(self) -> None:
        audit = PaperOperationAuditTimelineReadService(self.ledger)

        with self.assertRaisesRegex(ValueError, "event_type_filter"):
            audit.rows(event_type_filter=" ")
        with self.assertRaisesRegex(ValueError, "unknown"):
            audit.rows(event_type_filter="ORDER_AMENDED")

    def test_instrument_filter_scopes_rows_and_totals_after_restart(self) -> None:
        self._submit(order_id="paper-audit-instrument-alpha")
        self.ledger.append(
            PaperEvent(
                event_id="EVT-audit-instrument-bravo",
                event_type=PaperEventType.RISK_DECISION,
                occurred_at=self.now + timedelta(minutes=1),
                order_id="paper-audit-instrument-bravo",
                instrument_id="FIXTURE:NSE:EQ:BRAVO",
                payload=json.dumps({"payload": {}}),
            )
        )

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        all_rows = restarted.rows(instrument_id_filter="ALL")
        bravo_rows = restarted.rows(instrument_id_filter="FIXTURE:NSE:EQ:BRAVO")
        bravo_summary = restarted.integrity(instrument_id_filter="FIXTURE:NSE:EQ:BRAVO")

        self.assertEqual(len(all_rows), 3)
        self.assertEqual([row.instrument_id for row in bravo_rows], ["FIXTURE:NSE:EQ:BRAVO"])
        self.assertEqual(bravo_summary.total_events, 1)
        self.assertEqual(bravo_summary.valid_events, 1)

    def test_instrument_filter_rejects_blank_or_unknown_values(self) -> None:
        audit = PaperOperationAuditTimelineReadService(self.ledger)

        with self.assertRaisesRegex(ValueError, "instrument_id_filter"):
            audit.rows(instrument_id_filter=" ")
        with self.assertRaisesRegex(ValueError, "unknown"):
            audit.rows(instrument_id_filter="FIXTURE:NSE:EQ:UNKNOWN")

    def test_time_window_filter_scopes_rows_and_totals_after_restart(self) -> None:
        submission = self._submit(order_id="paper-audit-time-window")
        fill_time = self.now + timedelta(minutes=1)
        self.service.fill(submission.order, fill_price=101, now=fill_time)

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        all_rows = restarted.rows()
        opening_rows = restarted.rows(start_time=self.now, end_time=self.now)
        fill_rows = restarted.rows(start_time=fill_time, end_time=fill_time)
        fill_summary = restarted.integrity(start_time=fill_time, end_time=fill_time)

        self.assertEqual(len(all_rows), 3)
        self.assertEqual([row.event_type for row in opening_rows], ["RISK_DECISION", "ORDER_SUBMITTED"])
        self.assertEqual([row.event_type for row in fill_rows], ["ORDER_FILLED"])
        self.assertEqual(fill_summary.total_events, 1)
        self.assertEqual(fill_summary.valid_events, 1)

    def test_time_window_filter_rejects_inverted_or_timezone_naive_bounds(self) -> None:
        audit = PaperOperationAuditTimelineReadService(self.ledger)

        with self.assertRaisesRegex(ValueError, "start_time"):
            audit.rows(start_time=self.now + timedelta(minutes=1), end_time=self.now)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            audit.rows(start_time=self.now.replace(tzinfo=None))

    def test_filter_summary_reports_all_and_fully_scoped_local_filters_after_restart(self) -> None:
        submission = self._submit(order_id="paper-audit-filter-summary")
        fill_time = self.now + timedelta(minutes=1)
        self.service.fill(submission.order, fill_price=101, now=fill_time)

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        all_summary = restarted.filter_summary()
        scoped_summary = restarted.filter_summary(
            order_id="paper-audit-filter-summary",
            integrity_filter="VALID",
            event_type_filter="ORDER_FILLED",
            instrument_id_filter="FIXTURE:NSE:EQ:ALPHA",
            side_filter="BUY",
            start_time=fill_time,
            end_time=fill_time,
        )

        self.assertEqual(all_summary.order_scope, "ALL")
        self.assertEqual(all_summary.integrity_scope, "ALL")
        self.assertEqual(all_summary.event_type_scope, "ALL")
        self.assertEqual(all_summary.instrument_scope, "ALL")
        self.assertEqual(all_summary.side_scope, "ALL")
        self.assertIsNone(all_summary.start_time)
        self.assertIsNone(all_summary.end_time)
        self.assertEqual(scoped_summary.order_scope, "paper-audit-filter-summary")
        self.assertEqual(scoped_summary.integrity_scope, "VALID")
        self.assertEqual(scoped_summary.event_type_scope, "ORDER_FILLED")
        self.assertEqual(scoped_summary.instrument_scope, "FIXTURE:NSE:EQ:ALPHA")
        self.assertEqual(scoped_summary.side_scope, "BUY")
        self.assertEqual(scoped_summary.start_time, fill_time)
        self.assertEqual(scoped_summary.end_time, fill_time)

    def test_filter_summary_rejects_invalid_time_window_without_repair(self) -> None:
        audit = PaperOperationAuditTimelineReadService(self.ledger)

        with self.assertRaisesRegex(ValueError, "start_time"):
            audit.filter_summary(start_time=self.now + timedelta(minutes=1), end_time=self.now)

    def test_scope_presets_resolve_all_valid_and_issue_views_after_restart(self) -> None:
        self._submit(order_id="paper-audit-preset-valid")
        self.ledger.append(
            PaperEvent(
                event_id="EVT-audit-preset-issue",
                event_type=PaperEventType.ORDER_FILLED,
                occurred_at=self.now + timedelta(minutes=1),
                order_id="paper-audit-preset-issue",
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                payload="not-json",
            )
        )

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        all_preset = restarted.scope_preset("ALL")
        valid_preset = restarted.scope_preset("VALID")
        issue_preset = restarted.scope_preset("ISSUES")

        self.assertEqual(all_preset.integrity_filter, "ALL")
        self.assertEqual(valid_preset.label, "Valid interpretations")
        self.assertEqual(issue_preset.label, "Integrity issues")
        self.assertEqual(
            len(restarted.rows(integrity_filter=all_preset.integrity_filter)),
            3,
        )
        self.assertEqual(
            len(restarted.rows(integrity_filter=valid_preset.integrity_filter)),
            2,
        )
        self.assertEqual(
            len(restarted.rows(integrity_filter=issue_preset.integrity_filter)),
            1,
        )

    def test_scope_preset_rejects_unknown_identity(self) -> None:
        audit = PaperOperationAuditTimelineReadService(self.ledger)

        with self.assertRaisesRegex(ValueError, "unknown"):
            audit.scope_preset("RECONCILED")

    def test_row_detail_resolves_retained_and_interpreted_fields_after_restart(self) -> None:
        submission = self._submit(order_id="paper-audit-row-detail")
        fill_time = self.now + timedelta(minutes=1)
        self.service.fill(submission.order, fill_price=101, now=fill_time)

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        fill_row = next(row for row in restarted.rows() if row.event_type == "ORDER_FILLED")
        detail = restarted.row_detail(fill_row.event_id)

        self.assertEqual(detail.row.event_id, fill_row.event_id)
        self.assertEqual(detail.row.lifecycle_state, "FILLED")
        self.assertTrue(detail.row.payload_valid)
        self.assertIn('"fill_price":101', detail.retained_payload)

    def test_row_detail_keeps_malformed_payload_visible_and_rejects_unknown_ids(self) -> None:
        malformed_event = PaperEvent(
            event_id="EVT-audit-row-detail-malformed",
            event_type=PaperEventType.RISK_DECISION,
            occurred_at=self.now,
            order_id="paper-audit-row-detail-malformed",
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            payload="not-json",
        )
        self.ledger.append(malformed_event)
        audit = PaperOperationAuditTimelineReadService(self.ledger)

        detail = audit.row_detail(malformed_event.event_id)
        self.assertFalse(detail.row.payload_valid)
        self.assertEqual(detail.retained_payload, "not-json")
        with self.assertRaisesRegex(ValueError, "event_id"):
            audit.row_detail(" ")
        with self.assertRaisesRegex(ValueError, "unknown"):
            audit.row_detail("EVT-audit-row-detail-unknown")

    def test_payload_side_filter_scopes_buy_and_sell_rows_after_restart(self) -> None:
        self._submit(order_id="paper-audit-side-buy", side=OrderSide.BUY)
        self._submit(order_id="paper-audit-side-sell", side=OrderSide.SELL)

        restarted = PaperOperationAuditTimelineReadService(SqlitePaperLedger(self.path))
        all_rows = restarted.rows()
        buy_rows = restarted.rows(side_filter="BUY")
        sell_rows = restarted.rows(side_filter="SELL")
        buy_summary = restarted.filter_summary(side_filter="BUY")
        sell_summary = restarted.filter_summary(side_filter="SELL")

        self.assertGreater(len(all_rows), len(buy_rows))
        self.assertGreater(len(buy_rows), 0)
        self.assertGreater(len(sell_rows), 0)
        self.assertEqual({row.side for row in buy_rows}, {"BUY"})
        self.assertEqual({row.side for row in sell_rows}, {"SELL"})
        self.assertEqual(buy_summary.side_scope, "BUY")
        self.assertEqual(sell_summary.side_scope, "SELL")

    def test_payload_side_filter_rejects_blank_or_unknown_values(self) -> None:
        audit = PaperOperationAuditTimelineReadService(self.ledger)

        with self.assertRaisesRegex(ValueError, "side_filter"):
            audit.rows(side_filter=" ")
        with self.assertRaisesRegex(ValueError, "unknown"):
            audit.rows(side_filter="HOLD")


if __name__ == "__main__":
    unittest.main()
