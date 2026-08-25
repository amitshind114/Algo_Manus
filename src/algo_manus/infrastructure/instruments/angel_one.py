"""Read-only public Angel One ScripMaster adapter.

This module downloads only Angel One's public instrument-master JSON.  It does
not authenticate, create a SmartAPI session, inspect an account, fetch market
prices, place paper orders, or route live orders.  The application layer calls
it explicitly through :class:`BrokerInstrumentMasterPort`; imports never
perform I/O and failed source records are rejected rather than substituted.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import datetime
from http.client import IncompleteRead
from typing import Any
from urllib.request import Request, urlopen

from algo_manus.domain.instruments import (
    Instrument,
    InstrumentMasterSnapshot,
    InstrumentStatus,
    InstrumentType,
    OptionType,
)

ANGEL_SCRIP_MASTER_URI = (
    "https://margincalculator.angelbroking.com/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)
_AMOUNT_SCALE = 100.0
_DOWNLOAD_CHUNK_BYTES = 1_048_576
_MAX_PUBLIC_DOWNLOAD_ATTEMPTS = 6


class AngelScripMasterDownloadError(RuntimeError):
    """Raised when the public ScripMaster source cannot be retrieved."""


class AngelScripMasterNormalizationError(ValueError):
    """Raised when a public source record cannot become a canonical instrument."""


def _public_fetch(uri: str) -> bytes:
    """Fetch the public master only when a manual sync invokes the adapter.

    The publisher has intermittently closed this large public file mid-transfer.
    A bounded range-resume loop completes the *same* explicit user invocation;
    it neither schedules a sync nor accesses an authenticated endpoint.
    """

    content = bytearray()
    expected_size: int | None = None
    last_error: Exception | None = None
    for _ in range(_MAX_PUBLIC_DOWNLOAD_ATTEMPTS):
        offset = len(content)
        headers = {"User-Agent": "AlgoManus public instrument master"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = Request(uri, headers=headers)
        completed = False
        try:
            with urlopen(request, timeout=60) as response:  # noqa: S310 - approved fixed public source
                status = getattr(response, "status", response.getcode())
                if offset and status != 206:
                    raise AngelScripMasterDownloadError(
                        "Angel One public ScripMaster did not honor a required range resume"
                    )
                expected_size = _expected_source_size(response.headers, offset)
                while chunk := response.read(_DOWNLOAD_CHUNK_BYTES):
                    content.extend(chunk)
                completed = True
        except (OSError, IncompleteRead) as exc:
            last_error = exc

        if expected_size is None and completed:
            return bytes(content)
        if expected_size is not None and len(content) == expected_size:
            return bytes(content)
        if completed:
            last_error = AngelScripMasterDownloadError(
                "Angel One public ScripMaster ended before its declared content length"
            )

    raise AngelScripMasterDownloadError(
        "Angel One public ScripMaster transfer was incomplete; no snapshot was created"
    ) from last_error


def _expected_source_size(headers: Mapping[str, str], offset: int) -> int | None:
    """Return a response's complete resource size, if the source declares it."""

    content_range = headers.get("Content-Range")
    if content_range and "/" in content_range:
        total = content_range.rsplit("/", maxsplit=1)[1]
        if total.isdigit():
            return int(total)
    content_length = headers.get("Content-Length")
    if content_length and content_length.isdigit():
        return offset + int(content_length)
    return None


class AngelScripMasterProvider:
    """Normalize Angel One's public master behind the broker-master port.

    ``fetcher`` is injectable solely for deterministic tests.  Production use
    defaults to the fixed public URI and is intentionally manual through the
    existing sync application service.
    """

    broker_name = "angel_one"

    def __init__(self, fetcher: Callable[[str], bytes] | None = None) -> None:
        self._fetcher = fetcher or _public_fetch

    def download_snapshot(self, *, downloaded_at: datetime) -> InstrumentMasterSnapshot:
        if downloaded_at.tzinfo is None:
            raise ValueError("downloaded_at must be timezone-aware")
        raw_content = self._fetcher(ANGEL_SCRIP_MASTER_URI)
        try:
            records = json.loads(raw_content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AngelScripMasterNormalizationError(
                "Angel One public ScripMaster must be UTF-8 JSON"
            ) from exc
        if not isinstance(records, list):
            raise AngelScripMasterNormalizationError(
                "Angel One public ScripMaster must contain a JSON list"
            )
        instruments = tuple(self._normalize_record(record, position) for position, record in enumerate(records))
        return InstrumentMasterSnapshot.create(
            broker=self.broker_name,
            source_uri=ANGEL_SCRIP_MASTER_URI,
            raw_content=raw_content,
            instruments=instruments,
            downloaded_at=downloaded_at,
        )

    @classmethod
    def _normalize_record(cls, record: object, position: int) -> Instrument:
        if not isinstance(record, Mapping):
            raise AngelScripMasterNormalizationError(
                f"Angel ScripMaster record {position} must be an object"
            )
        source = {str(key): value for key, value in record.items()}
        token = cls._required_text(source, "token", position)
        symbol = cls._required_text(source, "symbol", position)
        segment = cls._required_text(source, "exch_seg", position).upper()
        name = str(source.get("name") or symbol).strip() or symbol
        raw_type = str(source.get("instrumenttype") or "").strip().upper()
        instrument_type = cls._instrument_type(raw_type, segment, symbol)
        expiry = cls._parse_expiry(source.get("expiry"), position)
        lot_size = cls._positive_int(source.get("lotsize"), "lotsize", position)
        tick_size = cls._scaled_positive(source.get("tick_size"), "tick_size", position)
        strike = cls._scaled_positive(source.get("strike"), "strike", position, required=False)

        option_type: OptionType | None = None
        if instrument_type is InstrumentType.OPTION:
            option_type = cls._option_type(symbol, position)
            if strike is None:
                raise AngelScripMasterNormalizationError(
                    f"Angel ScripMaster record {position} requires a positive strike for an option"
                )
        else:
            strike = None
        if instrument_type in {InstrumentType.FUTURE, InstrumentType.OPTION}:
            if expiry is None:
                raise AngelScripMasterNormalizationError(
                    f"Angel ScripMaster record {position} requires expiry for a derivative"
                )
            if lot_size is None or tick_size is None:
                raise AngelScripMasterNormalizationError(
                    f"Angel ScripMaster record {position} requires lot size and tick size for a derivative"
                )
        else:
            expiry = None
            lot_size = lot_size if lot_size and lot_size > 0 else None
            tick_size = tick_size if tick_size and tick_size > 0 else None

        metadata = {
            "source_instrumenttype": raw_type,
            "source_name": name,
            "source_status": "not_provided",
        }
        return Instrument(
            broker=cls.broker_name,
            exchange=segment,
            segment=segment,
            broker_token=token,
            trading_symbol=symbol,
            display_name=name,
            instrument_type=instrument_type,
            status=InstrumentStatus.ACTIVE,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            lot_size=lot_size,
            tick_size=tick_size,
            metadata=metadata,
        )

    @staticmethod
    def _required_text(source: Mapping[str, Any], field: str, position: int) -> str:
        value = str(source.get(field) or "").strip()
        if not value:
            raise AngelScripMasterNormalizationError(
                f"Angel ScripMaster record {position} requires {field}"
            )
        return value

    @staticmethod
    def _instrument_type(raw_type: str, segment: str, symbol: str) -> InstrumentType:
        if raw_type.startswith("OPT"):
            return InstrumentType.OPTION
        if raw_type.startswith("FUT"):
            return InstrumentType.FUTURE
        if raw_type == "UNDCUR":
            return InstrumentType.CURRENCY
        if raw_type == "UNDCOM":
            return InstrumentType.COMMODITY
        if raw_type.startswith("UNDIR"):
            return InstrumentType.INDEX
        if raw_type == "INDEX":
            return InstrumentType.INDEX
        if "IDX" in raw_type or raw_type == "AMXIDX":
            return InstrumentType.INDEX
        if raw_type.startswith("COM") or segment == "MCX":
            return InstrumentType.COMMODITY
        if symbol.upper().endswith("-EQ") or segment in {"NSE", "BSE"}:
            return InstrumentType.EQUITY
        raise AngelScripMasterNormalizationError(
            f"Angel ScripMaster record has unsupported instrument type {raw_type or '<empty>'}"
        )

    @staticmethod
    def _parse_expiry(value: object, position: int):
        raw = str(value or "").strip()
        if not raw:
            return None
        for pattern in ("%d%b%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.upper(), pattern).date()
            except ValueError:
                continue
        raise AngelScripMasterNormalizationError(
            f"Angel ScripMaster record {position} has unsupported expiry {raw!r}"
        )

    @staticmethod
    def _positive_int(value: object, field: str, position: int) -> int | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = int(float(raw))
        except ValueError as exc:
            raise AngelScripMasterNormalizationError(
                f"Angel ScripMaster record {position} has invalid {field}"
            ) from exc
        return parsed if parsed > 0 else None

    @staticmethod
    def _scaled_positive(
        value: object, field: str, position: int, *, required: bool = False
    ) -> float | None:
        raw = str(value or "").strip()
        if not raw:
            if required:
                raise AngelScripMasterNormalizationError(
                    f"Angel ScripMaster record {position} requires {field}"
                )
            return None
        try:
            parsed = float(raw) / _AMOUNT_SCALE
        except ValueError as exc:
            raise AngelScripMasterNormalizationError(
                f"Angel ScripMaster record {position} has invalid {field}"
            ) from exc
        return parsed if parsed > 0 else None

    @staticmethod
    def _option_type(symbol: str, position: int) -> OptionType:
        normalized = symbol.upper()
        if normalized.endswith("CE"):
            return OptionType.CALL
        if normalized.endswith("PE"):
            return OptionType.PUT
        embedded_option = re.search(r"(CE|PE)(?=\d)", normalized)
        if embedded_option and embedded_option.group(1) == "CE":
            return OptionType.CALL
        if embedded_option and embedded_option.group(1) == "PE":
            return OptionType.PUT
        raise AngelScripMasterNormalizationError(
            f"Angel ScripMaster record {position} option symbol must contain a CE or PE option marker"
        )
