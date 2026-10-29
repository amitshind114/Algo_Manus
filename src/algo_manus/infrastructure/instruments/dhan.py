"""Read-only Dhan public instrument-master adapter.

The adapter consumes Dhan's published detailed CSV only when an explicit
application sync invokes it. It does not authenticate, access account data,
retrieve prices, place orders, open a WebSocket, schedule work, or fall back to
fixtures. Every accepted response becomes an immutable local snapshot through
the existing ``InstrumentMasterSnapshot`` contract.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Mapping
from datetime import date, datetime
from io import StringIO
from urllib.request import Request, urlopen

from algo_manus.domain.instruments import (
    Instrument,
    InstrumentMasterSnapshot,
    InstrumentStatus,
    InstrumentType,
    OptionType,
)

DHAN_INSTRUMENT_MASTER_URI = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
_DOWNLOAD_CHUNK_BYTES = 1_048_576

_REQUIRED_COLUMNS = frozenset(
    {
        "EXCH_ID",
        "SEGMENT",
        "SECURITY_ID",
        "SYMBOL_NAME",
        "DISPLAY_NAME",
        "INSTRUMENT",
        "INSTRUMENT_TYPE",
        "LOT_SIZE",
        "SM_EXPIRY_DATE",
        "STRIKE_PRICE",
        "OPTION_TYPE",
        "TICK_SIZE",
    }
)


class DhanInstrumentMasterDownloadError(RuntimeError):
    """Raised when the fixed public Dhan master cannot be downloaded."""


class DhanInstrumentMasterNormalizationError(ValueError):
    """Raised when a Dhan public CSV record cannot become a canonical instrument."""


def _public_fetch(uri: str) -> bytes:
    """Download the fixed public CSV only during an explicit manual sync."""

    request = Request(uri, headers={"User-Agent": "AlgoManus public Dhan instrument master"})
    try:
        with urlopen(request, timeout=120) as response:  # noqa: S310 - fixed public source
            content = bytearray()
            while chunk := response.read(_DOWNLOAD_CHUNK_BYTES):
                content.extend(chunk)
            return bytes(content)
    except OSError as exc:
        raise DhanInstrumentMasterDownloadError(
            "Dhan public instrument master transfer failed; no snapshot was created"
        ) from exc


class DhanInstrumentMasterProvider:
    """Normalize Dhan's detailed public master behind the broker-master port."""

    broker_name = "dhan"

    def __init__(self, fetcher: Callable[[str], bytes] | None = None) -> None:
        self._fetcher = fetcher or _public_fetch

    def download_snapshot(self, *, downloaded_at: datetime) -> InstrumentMasterSnapshot:
        if downloaded_at.tzinfo is None:
            raise ValueError("downloaded_at must be timezone-aware")
        raw_content = self._fetcher(DHAN_INSTRUMENT_MASTER_URI)
        try:
            text = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DhanInstrumentMasterNormalizationError(
                "Dhan public instrument master must be UTF-8 CSV"
            ) from exc

        reader = csv.DictReader(StringIO(text, newline=""))
        fieldnames = frozenset(reader.fieldnames or ())
        missing = sorted(_REQUIRED_COLUMNS - fieldnames)
        if missing:
            raise DhanInstrumentMasterNormalizationError(
                f"Dhan public instrument master is missing columns: {', '.join(missing)}"
            )

        records = tuple(reader)
        if not records:
            raise DhanInstrumentMasterNormalizationError(
                "Dhan public instrument master must contain at least one record"
            )
        instruments = tuple(
            self._normalize_record(record, position)
            for position, record in enumerate(records)
        )
        try:
            return InstrumentMasterSnapshot.create(
                broker=self.broker_name,
                source_uri=DHAN_INSTRUMENT_MASTER_URI,
                raw_content=raw_content,
                instruments=instruments,
                downloaded_at=downloaded_at,
            )
        except ValueError as exc:
            raise DhanInstrumentMasterNormalizationError(
                f"Dhan public instrument master contains invalid identities: {exc}"
            ) from exc

    @classmethod
    def _normalize_record(cls, record: Mapping[str, str | None], position: int) -> Instrument:
        source = {key: (value or "").strip() for key, value in record.items()}
        exchange = cls._required_text(source, "EXCH_ID", position).upper()
        source_segment = cls._required_text(source, "SEGMENT", position).upper()
        token = cls._required_text(source, "SECURITY_ID", position)
        symbol = cls._required_text(source, "SYMBOL_NAME", position)
        display_name = source.get("DISPLAY_NAME") or symbol
        instrument_code = cls._required_text(source, "INSTRUMENT", position).upper()
        raw_type = source.get("INSTRUMENT_TYPE", "")
        instrument_type = cls._instrument_type(instrument_code, source_segment, position)
        segment = cls._canonical_segment(exchange, source_segment, position)
        expiry = cls._parse_expiry(source.get("SM_EXPIRY_DATE", ""), position)
        lot_size = cls._positive_int(source.get("LOT_SIZE", ""), "LOT_SIZE", position)
        tick_size = cls._positive_float(source.get("TICK_SIZE", ""), "TICK_SIZE", position)
        strike = cls._positive_float(source.get("STRIKE_PRICE", ""), "STRIKE_PRICE", position)
        option_type = cls._option_type(source.get("OPTION_TYPE", ""), position)

        if instrument_type in {InstrumentType.FUTURE, InstrumentType.OPTION}:
            if expiry is None:
                raise DhanInstrumentMasterNormalizationError(
                    f"Dhan record {position} requires expiry for {instrument_type.value.lower()}"
                )
            if lot_size is None or tick_size is None:
                raise DhanInstrumentMasterNormalizationError(
                    f"Dhan record {position} requires positive lot size and tick size"
                )
        else:
            expiry = None
            strike = None
            option_type = None
            lot_size = lot_size if lot_size and lot_size > 0 else None
            tick_size = tick_size if tick_size and tick_size > 0 else None

        if instrument_type is InstrumentType.OPTION:
            if strike is None or option_type is None:
                raise DhanInstrumentMasterNormalizationError(
                    f"Dhan record {position} requires positive strike and CE/PE option type"
                )

        return Instrument(
            broker=cls.broker_name,
            exchange=exchange,
            segment=segment,
            broker_token=token,
            trading_symbol=symbol,
            display_name=display_name,
            instrument_type=instrument_type,
            status=InstrumentStatus.ACTIVE,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            lot_size=lot_size,
            tick_size=tick_size,
            metadata={
                "source_exchange": exchange,
                "source_segment": source_segment,
                "source_instrument": instrument_code,
                "source_instrument_type": raw_type,
                "source_series": source.get("SERIES", ""),
                "source_isin": source.get("ISIN", ""),
                "source_underlying_security_id": source.get("UNDERLYING_SECURITY_ID", ""),
                "source_underlying_symbol": source.get("UNDERLYING_SYMBOL", ""),
            },
        )

    @staticmethod
    def _required_text(source: Mapping[str, str], field: str, position: int) -> str:
        value = source.get(field, "").strip()
        if not value:
            raise DhanInstrumentMasterNormalizationError(
                f"Dhan record {position} requires {field}"
            )
        return value

    @staticmethod
    def _instrument_type(code: str, source_segment: str, position: int) -> InstrumentType:
        if code == "INDEX" or source_segment == "I":
            return InstrumentType.INDEX
        if code.startswith("OPT"):
            return InstrumentType.OPTION
        if code.startswith("FUT"):
            return InstrumentType.FUTURE
        if source_segment in {"E", "G"} or code in {"EQUITY", "ETF"}:
            return InstrumentType.EQUITY
        raise DhanInstrumentMasterNormalizationError(
            f"Dhan record {position} has unsupported instrument {code!r} in segment {source_segment!r}"
        )

    @staticmethod
    def _canonical_segment(exchange: str, source_segment: str, position: int) -> str:
        if source_segment == "E" or source_segment == "G":
            return f"{exchange}_EQ"
        if source_segment == "I":
            return "IDX_I"
        if source_segment == "D":
            return f"{exchange}_FNO"
        if source_segment == "C":
            return f"{exchange}_CURRENCY"
        if source_segment == "M":
            return "MCX_COMM" if exchange == "MCX" else f"{exchange}_COMM"
        raise DhanInstrumentMasterNormalizationError(
            f"Dhan record {position} has unsupported segment {source_segment!r}"
        )

    @staticmethod
    def _parse_expiry(value: str, position: int) -> date | None:
        raw = value.strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise DhanInstrumentMasterNormalizationError(
                f"Dhan record {position} has invalid SM_EXPIRY_DATE {raw!r}"
            ) from exc

    @staticmethod
    def _positive_int(value: str, field: str, position: int) -> int | None:
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = int(float(raw))
        except ValueError as exc:
            raise DhanInstrumentMasterNormalizationError(
                f"Dhan record {position} has invalid {field}"
            ) from exc
        return parsed if parsed > 0 else None

    @staticmethod
    def _positive_float(value: str, field: str, position: int) -> float | None:
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = float(raw)
        except ValueError as exc:
            raise DhanInstrumentMasterNormalizationError(
                f"Dhan record {position} has invalid {field}"
            ) from exc
        return parsed if parsed > 0 else None

    @staticmethod
    def _option_type(value: str, position: int) -> OptionType | None:
        raw = value.strip().upper()
        if not raw or raw == "XX":
            return None
        if raw == "CE":
            return OptionType.CALL
        if raw == "PE":
            return OptionType.PUT
        raise DhanInstrumentMasterNormalizationError(
            f"Dhan record {position} has unsupported OPTION_TYPE {raw!r}"
        )
