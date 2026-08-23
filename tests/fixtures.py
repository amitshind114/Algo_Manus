"""Network-free broker-master fixtures used by Phase 1 tests."""

from __future__ import annotations

from datetime import datetime, timezone

from algo_manus.domain.instruments import (
    Instrument,
    InstrumentMasterSnapshot,
    InstrumentStatus,
    InstrumentType,
)


def instrument(
    *,
    token: str,
    symbol: str,
    display_name: str,
    status: InstrumentStatus = InstrumentStatus.ACTIVE,
) -> Instrument:
    return Instrument(
        broker="angel_one",
        exchange="NSE",
        segment="NSE",
        broker_token=token,
        trading_symbol=symbol,
        display_name=display_name,
        instrument_type=InstrumentType.EQUITY,
        status=status,
        lot_size=1,
        tick_size=0.05,
    )


def snapshot(
    *,
    content: bytes = b"fixture-master-v1",
    downloaded_at: datetime | None = None,
    instruments: tuple[Instrument, ...] | None = None,
) -> InstrumentMasterSnapshot:
    return InstrumentMasterSnapshot.create(
        broker="angel_one",
        source_uri="fixture://angel-one/instrument-master",
        raw_content=content,
        downloaded_at=downloaded_at or datetime(2026, 8, 23, 9, 0, tzinfo=timezone.utc),
        instruments=instruments
        or (
            instrument(token="500325", symbol="RELIANCE-EQ", display_name="RELIANCE INDUSTRIES"),
            instrument(token="532540", symbol="TCS-EQ", display_name="TATA CONSULTANCY"),
        ),
    )
