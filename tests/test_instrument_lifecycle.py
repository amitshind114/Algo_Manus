"""Option I acceptance tests for India-first retained instrument lifecycle views."""

from __future__ import annotations

from datetime import date, datetime, timezone
import unittest

from algo_manus.application.instrument_lifecycle import (
    InstrumentLifecycleReadService,
    InstrumentLifecycleState,
)
from algo_manus.domain.instruments import (
    Instrument,
    InstrumentMasterSnapshot,
    InstrumentStatus,
    InstrumentType,
    OptionType,
)


def _snapshot(*instruments: Instrument, content: bytes = b"instrument-lifecycle") -> InstrumentMasterSnapshot:
    return InstrumentMasterSnapshot.create(
        broker="angel_one",
        source_uri="local://retained-angel-scrip-master",
        raw_content=content,
        instruments=instruments,
        downloaded_at=datetime(2026, 8, 26, 9, 15, tzinfo=timezone.utc),
    )


def _option(*, lot_size: int = 75, status: InstrumentStatus = InstrumentStatus.ACTIVE) -> Instrument:
    return Instrument(
        broker="angel_one",
        exchange="NFO",
        segment="NFO",
        broker_token="46725",
        trading_symbol="NIFTY26SEP25000CE",
        display_name="NIFTY",
        instrument_type=InstrumentType.OPTION,
        expiry=date(2026, 9, 24),
        strike=25_000,
        option_type=OptionType.CALL,
        lot_size=lot_size,
        tick_size=0.05,
        status=status,
    )


class InstrumentLifecycleReadServiceTests(unittest.TestCase):
    """Exercise local metadata/review projection; no provider or price feed is involved."""

    def test_projects_nse_nfo_and_mcx_contract_fields_and_summary_counts(self) -> None:
        equity = Instrument(
            broker="angel_one", exchange="NSE", segment="NSE", broker_token="500325",
            trading_symbol="RELIANCE-EQ", display_name="RELIANCE INDUSTRIES",
            instrument_type=InstrumentType.EQUITY, lot_size=1, tick_size=0.05,
        )
        option = _option()
        future = Instrument(
            broker="angel_one", exchange="MCX", segment="MCX", broker_token="60001",
            trading_symbol="GOLDM26OCTFUT", display_name="GOLDM",
            instrument_type=InstrumentType.FUTURE, expiry=date(2026, 10, 5), lot_size=100,
            tick_size=1.0,
        )

        projection = InstrumentLifecycleReadService().project(_snapshot(equity, option, future))

        by_id = {item.instrument_id: item for item in projection.instruments}
        self.assertEqual(by_id[option.instrument_id].expiry, date(2026, 9, 24))
        self.assertEqual(by_id[option.instrument_id].strike, 25_000)
        self.assertEqual(by_id[option.instrument_id].option_type, "CE")
        self.assertEqual(by_id[option.instrument_id].lot_size, 75)
        self.assertEqual(by_id[option.instrument_id].tick_size, 0.05)
        self.assertEqual(by_id[future.instrument_id].exchange, "MCX")
        self.assertEqual(projection.summary.derivative_count, 2)
        self.assertEqual(projection.summary.segment_counts, {"MCX": 1, "NFO": 1, "NSE": 1})
        self.assertEqual(projection.summary.review_required_count, 0)
        self.assertEqual(by_id[equity.instrument_id].lifecycle_state, InstrumentLifecycleState.READY)

    def test_contract_change_deactivation_expiry_and_missing_records_require_review(self) -> None:
        baseline_option = _option(lot_size=75)
        inactive_equity = Instrument(
            broker="angel_one", exchange="NSE", segment="NSE", broker_token="532540",
            trading_symbol="TCS-EQ", display_name="TATA CONSULTANCY",
            instrument_type=InstrumentType.EQUITY, lot_size=1, tick_size=0.05,
        )
        expiring_future = Instrument(
            broker="angel_one", exchange="NFO", segment="NFO", broker_token="90001",
            trading_symbol="BANKNIFTY26SEPFUT", display_name="BANKNIFTY",
            instrument_type=InstrumentType.FUTURE, expiry=date(2026, 9, 24), lot_size=30,
            tick_size=0.05,
        )
        baseline = _snapshot(baseline_option, inactive_equity, expiring_future, content=b"baseline")
        current = _snapshot(
            _option(lot_size=65),
            Instrument(
                broker="angel_one", exchange="NSE", segment="NSE", broker_token="532540",
                trading_symbol="TCS-EQ", display_name="TATA CONSULTANCY",
                instrument_type=InstrumentType.EQUITY, lot_size=1, tick_size=0.05,
                status=InstrumentStatus.INACTIVE,
            ),
            content=b"current",
        )

        projection = InstrumentLifecycleReadService().project(current, baseline_snapshot=baseline)
        by_id = {item.instrument_id: item for item in projection.instruments}

        self.assertEqual(by_id[baseline_option.instrument_id].lifecycle_state, InstrumentLifecycleState.REVIEW_REQUIRED)
        self.assertIn("lot_size", by_id[baseline_option.instrument_id].review_reason or "")
        self.assertTrue(by_id[baseline_option.instrument_id].review_required)
        self.assertEqual(by_id[inactive_equity.instrument_id].lifecycle_state, InstrumentLifecycleState.INACTIVE)
        self.assertTrue(by_id[inactive_equity.instrument_id].review_required)
        self.assertEqual(by_id[expiring_future.instrument_id].lifecycle_state, InstrumentLifecycleState.MISSING)
        self.assertTrue(by_id[expiring_future.instrument_id].review_required)
        self.assertEqual(projection.summary.review_required_count, 3)

    def test_expired_and_unresolved_current_records_remain_visible_and_not_ready(self) -> None:
        expired = Instrument(
            broker="angel_one", exchange="NFO", segment="NFO", broker_token="70001",
            trading_symbol="NIFTY26AUGFUT", display_name="NIFTY",
            instrument_type=InstrumentType.FUTURE, expiry=date(2026, 8, 27), lot_size=75,
            tick_size=0.05, status=InstrumentStatus.EXPIRED,
        )
        unresolved = Instrument(
            broker="angel_one", exchange="BSE", segment="BSE", broker_token="500112",
            trading_symbol="SBIN-A", display_name="STATE BANK OF INDIA",
            instrument_type=InstrumentType.EQUITY, lot_size=1, tick_size=0.05,
            status=InstrumentStatus.UNRESOLVED,
        )

        projection = InstrumentLifecycleReadService().project(_snapshot(expired, unresolved))
        states = {item.instrument_id: item.lifecycle_state for item in projection.instruments}

        self.assertEqual(states[expired.instrument_id], InstrumentLifecycleState.EXPIRED)
        self.assertEqual(states[unresolved.instrument_id], InstrumentLifecycleState.UNRESOLVED)
        self.assertEqual(projection.summary.ready_count, 0)
        self.assertEqual(projection.summary.review_required_count, 2)

    def test_rejects_cross_broker_comparison_and_exposes_no_sync_or_execution_capability(self) -> None:
        current = _snapshot(_option())
        other = InstrumentMasterSnapshot.create(
            broker="other_broker", source_uri="local://other", raw_content=b"other",
            instruments=(Instrument(
                broker="other_broker", exchange="NSE", segment="NSE", broker_token="1",
                trading_symbol="OTHER-EQ", display_name="OTHER", instrument_type=InstrumentType.EQUITY,
            ),),
            downloaded_at=datetime(2026, 8, 26, 9, 15, tzinfo=timezone.utc),
        )
        service = InstrumentLifecycleReadService()

        with self.assertRaisesRegex(ValueError, "same broker"):
            service.project(current, baseline_snapshot=other)
        self.assertFalse(hasattr(service, "sync"))
        self.assertFalse(hasattr(service, "download"))
        self.assertFalse(hasattr(service, "submit"))


if __name__ == "__main__":
    unittest.main()
