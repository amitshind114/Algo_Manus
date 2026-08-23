from __future__ import annotations

from datetime import date, datetime, timezone
import unittest

from algo_manus.domain.execution import (
    ExecutionOrder,
    Fill,
    InvalidOrderTransition,
    OrderStatus,
    ReconciliationDisposition,
    ReconciliationRecord,
)
from algo_manus.domain.instruments import Instrument, InstrumentStatus, InstrumentType, OptionType
from algo_manus.domain.risk import OrderIntent, OrderSide


class InstrumentContractTests(unittest.TestCase):
    def _derivative(self, instrument_type: InstrumentType, **overrides) -> Instrument:
        values = {
            "broker": "FIXTURE",
            "exchange": "NFO",
            "segment": "NFO-OPT",
            "broker_token": "10001",
            "trading_symbol": "NIFTY26SEP25000CE",
            "display_name": "NIFTY fixture option",
            "instrument_type": instrument_type,
            "status": InstrumentStatus.ACTIVE,
            "expiry": date(2026, 9, 24),
            "strike": 25_000.0 if instrument_type is InstrumentType.OPTION else None,
            "option_type": OptionType.CALL if instrument_type is InstrumentType.OPTION else None,
            "lot_size": 75,
            "tick_size": 0.05,
        }
        values.update(overrides)
        return Instrument(**values)

    def test_option_contract_requires_complete_derivative_metadata(self) -> None:
        option = self._derivative(InstrumentType.OPTION)

        self.assertTrue(option.is_derivative)
        self.assertEqual(option.contract_descriptor, "NIFTY26SEP25000CE 2026-09-24 25000 CE")
        with self.assertRaisesRegex(ValueError, "positive strike"):
            self._derivative(InstrumentType.OPTION, strike=0.0)
        with self.assertRaisesRegex(ValueError, "lot_size and tick_size"):
            self._derivative(InstrumentType.OPTION, lot_size=None)

    def test_future_requires_expiry_but_not_option_fields(self) -> None:
        future = self._derivative(
            InstrumentType.FUTURE,
            segment="NFO-FUT",
            trading_symbol="NIFTY26SEP FUT",
            display_name="NIFTY fixture future",
        )

        self.assertTrue(future.is_derivative)
        self.assertEqual(future.contract_descriptor, "NIFTY26SEP FUT 2026-09-24")
        with self.assertRaisesRegex(ValueError, "requires expiry"):
            self._derivative(InstrumentType.FUTURE, expiry=None)
        with self.assertRaisesRegex(ValueError, "only valid for option"):
            self._derivative(InstrumentType.FUTURE, strike=25_000.0)


class ExecutionContractTests(unittest.TestCase):
    def _intent(self) -> OrderIntent:
        return OrderIntent(
            order_id="intent-1",
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            side=OrderSide.BUY,
            quantity=10,
            reference_price=100.0,
            strategy_revision_id="PARAM-test",
        )

    def test_order_transitions_and_fills_are_immutable_and_quantity_bound(self) -> None:
        created_at = datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc)
        order = ExecutionOrder.create(self._intent(), created_at=created_at)
        submitted = order.transition(OrderStatus.SUBMITTED, occurred_at=created_at)
        partial_fill = Fill(
            fill_id="fill-1",
            order_id="intent-1",
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            side=OrderSide.BUY,
            quantity=4,
            price=101.0,
            occurred_at=datetime(2026, 8, 23, 9, 16, tzinfo=timezone.utc),
        )
        partial = submitted.record_fill(partial_fill)
        final = partial.record_fill(
            Fill(
                fill_id="fill-2",
                order_id="intent-1",
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                side=OrderSide.BUY,
                quantity=6,
                price=102.0,
                occurred_at=datetime(2026, 8, 23, 9, 17, tzinfo=timezone.utc),
            )
        )

        self.assertEqual(order.status, OrderStatus.CREATED)
        self.assertEqual(partial.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(partial.filled_quantity, 4)
        self.assertEqual(final.status, OrderStatus.FILLED)
        self.assertEqual(final.remaining_quantity, 0)
        self.assertFalse(hasattr(final, "pnl"))
        with self.assertRaisesRegex(InvalidOrderTransition, "cannot transition"):
            final.transition(OrderStatus.CANCELLED, occurred_at=datetime(2026, 8, 23, 9, 18, tzinfo=timezone.utc))

    def test_fill_and_reconciliation_contracts_reject_invalid_identity_and_time(self) -> None:
        now = datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc)
        order = ExecutionOrder.create(self._intent(), created_at=now).transition(OrderStatus.SUBMITTED, occurred_at=now)
        wrong_fill = Fill(
            fill_id="fill-1",
            order_id="other-order",
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            side=OrderSide.BUY,
            quantity=1,
            price=100.0,
            occurred_at=now,
        )

        with self.assertRaisesRegex(ValueError, "same order"):
            order.record_fill(wrong_fill)
        record = ReconciliationRecord(
            reconciliation_id="recon-1",
            order_id="intent-1",
            disposition=ReconciliationDisposition.MATCHED,
            reason="local and external projections agree",
            occurred_at=now,
        )
        self.assertEqual(record.disposition, ReconciliationDisposition.MATCHED)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            ReconciliationRecord(
                reconciliation_id="recon-2",
                order_id="intent-1",
                disposition=ReconciliationDisposition.UNRESOLVED,
                reason="missing external evidence",
                occurred_at=datetime(2026, 8, 23, 9, 15),
            )


if __name__ == "__main__":
    unittest.main()
