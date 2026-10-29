"""Read-only Dhan historical-candle adapter.

This adapter implements the existing provider-neutral market-data port for
Dhan historical daily and intraday candles. It intentionally does not access
account data, positions, holdings, funds, order endpoints, live market feeds,
WebSockets, schedulers, or any execution capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from zoneinfo import ZoneInfo

from algo_manus.domain.market_data import (
    Candle,
    CandleDataset,
    DataProvenance,
    DataSourceKind,
    DataUseCase,
)
from algo_manus.infrastructure.market_data.dhan_client import (
    DHAN_DAILY_CANDLE_URI,
    DHAN_INTRADAY_CANDLE_URI,
    DhanRateLimitTransportError,
    DhanTransportError,
    _Transport,
    post_json,
)

_EQUITY_SEGMENTS = frozenset({"NSE_EQ", "BSE_EQ"})
_DHAN_INTERVALS = {"1m": 1, "5m": 5, "15m": 15, "25m": 25, "60m": 60}
_INTRADAY_MAX_REQUEST_WINDOW = timedelta(days=90)


class DhanHistoricalConfigurationError(ValueError):
    """Raised when local read-only Dhan configuration is absent or incomplete."""


class DhanHistoricalRequestError(ValueError):
    """Raised when Dhan returns a transport, authentication, or provider failure."""


class DhanHistoricalRateLimitError(DhanHistoricalRequestError):
    """Raised when Dhan rejects a request because of a rate limit."""


class DhanHistoricalResponseError(ValueError):
    """Raised when Dhan returns a malformed or invalid historical-candle response."""


class DhanHistoricalInstrumentError(ValueError):
    """Raised when a canonical instrument cannot be mapped to Dhan identifiers."""


class DhanHistoricalIntervalError(ValueError):
    """Raised when an interval is unsupported by the Dhan historical adapter."""


@dataclass(frozen=True, slots=True)
class DhanHistoricalCredentials:
    """Secret values supplied only by user-managed local environment configuration."""

    access_token: str

    def __post_init__(self) -> None:
        if not self.access_token.strip():
            raise DhanHistoricalConfigurationError(
                "ALGO_MANUS_DHAN_ACCESS_TOKEN is required"
            )


class DhanHistoricalCandleProvider:
    """Normalize documented Dhan historical candles behind MarketDataProviderPort.

    Dhan exposes up to five years of intraday history, but each request is
    locally bounded to 90 days to keep response sizes manageable. A single
    explicit ``fetch_candles`` action may therefore issue sequential 90-day
    requests. There is no scheduler, background work, retry, or silent resume.

    The adapter accepts a user-managed Dhan access token only. It does not know
    or use client PIN, TOTP, order endpoints, account endpoints, positions,
    holdings, funds, live feeds, or WebSockets. ``transport`` is injectable
    exclusively for deterministic tests.
    """

    source_name = "dhan"
    source_kind = DataSourceKind.BROKER

    def __init__(
        self,
        *,
        credentials: DhanHistoricalCredentials | None,
        transport: _Transport | None = None,
        configuration_error: str | None = None,
    ) -> None:
        self._credentials = credentials
        self._transport = transport or post_json
        self._configuration_error = configuration_error

    @classmethod
    def from_environment(cls) -> "DhanHistoricalCandleProvider":
        """Load local-only configuration without exposing or persisting secrets."""

        access_token = os.environ.get("ALGO_MANUS_DHAN_ACCESS_TOKEN", "").strip()
        if not access_token:
            return cls(credentials=None)
        return cls(credentials=DhanHistoricalCredentials(access_token=access_token))

    @property
    def credentials_configured(self) -> bool:
        return self._credentials is not None and self._configuration_error is None

    @property
    def configuration_message(self) -> str:
        return self._configuration_error or "ALGO_MANUS_DHAN_ACCESS_TOKEN is required"

    def fetch_candles(
        self,
        *,
        instrument_id: str,
        interval: str,
        start: datetime,
        end: datetime,
        retrieved_at: datetime,
    ) -> CandleDataset:
        """Fetch and combine one explicit, bounded research-only retrieval."""

        if not self.credentials_configured:
            raise DhanHistoricalConfigurationError(self.configuration_message)
        if start.tzinfo is None or end.tzinfo is None or retrieved_at.tzinfo is None:
            raise ValueError("historical-candle timestamps must be timezone-aware")
        if start >= end:
            raise ValueError("historical-candle start must be earlier than end")
        if retrieved_at < end:
            raise ValueError("retrieval time must not precede the requested end")

        segment, security_id = self._parse_instrument_id(instrument_id)
        is_daily = interval == "1d"
        if not is_daily and interval not in _DHAN_INTERVALS:
            raise DhanHistoricalIntervalError(
                f"unsupported Dhan historical interval {interval!r}"
            )
        instrument = self._instrument_for_segment(segment)
        ranges = (
            ((start, end),)
            if is_daily
            else tuple(self._intraday_ranges(start, end))
        )

        raw_chunks: list[bytes] = []
        combined: list[Candle] = []
        previous_timestamp: datetime | None = None
        for chunk_start, chunk_end in ranges:
            raw_content = self._request_chunk(
                segment=segment,
                security_id=security_id,
                instrument=instrument,
                interval=interval,
                start=chunk_start,
                end=chunk_end,
                is_daily=is_daily,
            )
            candles = self._parse_response(raw_content)
            if previous_timestamp is not None and candles[0].timestamp <= previous_timestamp:
                raise DhanHistoricalResponseError(
                    "Dhan historical chunks overlap or are not strictly chronological"
                )
            raw_chunks.append(raw_content)
            combined.extend(candles)
            previous_timestamp = candles[-1].timestamp

        return CandleDataset.create(
            instrument_id=instrument_id,
            interval=interval,
            provenance=DataProvenance(
                source_name=self.source_name,
                source_kind=self.source_kind,
                source_uri=DHAN_DAILY_CANDLE_URI if is_daily else DHAN_INTRADAY_CANDLE_URI,
                retrieved_at=retrieved_at,
                raw_content_sha256=sha256(b"".join(raw_chunks)).hexdigest(),
                adjustment_basis="unadjusted/unknown broker historical candles",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=tuple(combined),
        )

    def _request_chunk(
        self,
        *,
        segment: str,
        security_id: str,
        instrument: str,
        interval: str,
        start: datetime,
        end: datetime,
        is_daily: bool,
    ) -> bytes:
        uri = DHAN_DAILY_CANDLE_URI if is_daily else DHAN_INTRADAY_CANDLE_URI
        payload = {
            "securityId": security_id,
            "exchangeSegment": segment,
            "instrument": instrument,
            "oi": False,
            "fromDate": self._format_daily_bound(start)
            if is_daily
            else self._format_intraday_bound(start),
            "toDate": self._format_daily_bound(end)
            if is_daily
            else self._format_intraday_bound(end),
        }
        if is_daily:
            payload["expiryCode"] = 0
        else:
            payload["interval"] = _DHAN_INTERVALS[interval]
        try:
            return self._transport(
                uri,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                self._headers(),
            )
        except DhanRateLimitTransportError as exc:
            raise DhanHistoricalRateLimitError(
                "Dhan historical-data rate limit reached; retry manually later"
            ) from exc
        except DhanTransportError as exc:
            raise DhanHistoricalRequestError(
                "Dhan historical-data transport request failed"
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise DhanHistoricalRequestError(
                "Dhan historical-data transport request failed"
            ) from exc

    @staticmethod
    def _intraday_ranges(
        start: datetime, end: datetime
    ) -> list[tuple[datetime, datetime]]:
        ranges: list[tuple[datetime, datetime]] = []
        chunk_start = start
        while chunk_start < end:
            chunk_end = min(chunk_start + _INTRADAY_MAX_REQUEST_WINDOW, end)
            ranges.append((chunk_start, chunk_end))
            chunk_start = chunk_end
        return ranges

    @staticmethod
    def _instrument_for_segment(segment: str) -> str:
        if segment not in _EQUITY_SEGMENTS:
            raise DhanHistoricalInstrumentError(
                "Dhan historical adapter currently supports only NSE_EQ and BSE_EQ equity instruments"
            )
        return "EQUITY"

    def _headers(self) -> dict[str, str]:
        assert self._credentials is not None
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "access-token": self._credentials.access_token,
        }

    @staticmethod
    def _parse_instrument_id(instrument_id: str) -> tuple[str, str]:
        parts = instrument_id.split(":")
        if len(parts) == 4 and parts[0] == "DHAN":
            _, _, segment, security_id = parts
        elif len(parts) == 3 and parts[0] == "DHAN":
            _, segment, security_id = parts
        else:
            raise DhanHistoricalInstrumentError(
                "Dhan historical data requires a DHAN:<exchange>:<segment>:<security_id> identity"
            )
        if not segment.strip() or not security_id.strip():
            raise DhanHistoricalInstrumentError(
                "Dhan canonical instrument identity requires a segment and security ID"
            )
        return segment, security_id

    @staticmethod
    def _format_daily_bound(value: datetime) -> str:
        return value.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")

    @staticmethod
    def _format_intraday_bound(value: datetime) -> str:
        return value.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _parse_response(raw_content: bytes) -> tuple[Candle, ...]:
        try:
            response = json.loads(raw_content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DhanHistoricalResponseError(
                "Dhan historical response must be UTF-8 JSON"
            ) from exc
        if not isinstance(response, dict):
            raise DhanHistoricalResponseError("Dhan historical response must be an object")
        status = response.get("status")
        if (
            status is False
            or status in ("failure", "FAILED")
            or response.get("errorCode")
            or response.get("errorcode")
        ):
            code = str(response.get("errorCode") or response.get("errorcode") or "unknown_error")
            if code in {"DH-904", "904", "805", "429"}:
                raise DhanHistoricalRateLimitError(
                    "Dhan historical-data rate limit response"
                )
            raise DhanHistoricalRequestError(
                f"Dhan historical-data request rejected: {code}"
            )

        required_arrays = ("open", "high", "low", "close", "volume", "timestamp")
        arrays: dict[str, list[object]] = {}
        for field in required_arrays:
            value = response.get(field)
            if not isinstance(value, list):
                raise DhanHistoricalResponseError(
                    f"Dhan historical response field {field!r} must be an array"
                )
            arrays[field] = value

        lengths = {len(arrays[field]) for field in required_arrays}
        if len(lengths) != 1:
            raise DhanHistoricalResponseError(
                "Dhan historical response arrays must have equal lengths"
            )
        if not lengths or next(iter(lengths)) == 0:
            raise DhanHistoricalResponseError(
                "Dhan historical response must contain at least one candle"
            )

        candles: list[Candle] = []
        previous_timestamp: datetime | None = None
        count = next(iter(lengths))
        for position in range(count):
            try:
                epoch_seconds = int(arrays["timestamp"][position])
                open_price = float(arrays["open"][position])
                high_price = float(arrays["high"][position])
                low_price = float(arrays["low"][position])
                close_price = float(arrays["close"][position])
                volume = float(arrays["volume"][position])
            except (TypeError, ValueError) as exc:
                raise DhanHistoricalResponseError(
                    f"Dhan historical candle {position} is malformed"
                ) from exc

            timestamp = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise DhanHistoricalResponseError(
                    f"Dhan historical candle {position} is duplicate or out of order"
                )
            if min(open_price, high_price, low_price, close_price) <= 0:
                raise DhanHistoricalResponseError(
                    f"Dhan historical candle {position} has non-positive OHLC values"
                )
            if high_price < max(open_price, low_price, close_price) or low_price > min(
                open_price, high_price, close_price
            ):
                raise DhanHistoricalResponseError(
                    f"Dhan historical candle {position} has inconsistent OHLC values"
                )
            if volume < 0:
                raise DhanHistoricalResponseError(
                    f"Dhan historical candle {position} has negative volume"
                )

            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                )
            )
            previous_timestamp = timestamp

        return tuple(candles)
