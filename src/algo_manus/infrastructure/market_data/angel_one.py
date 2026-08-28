"""Read-only Angel One historical-candle adapter.

This module posts only to Angel One's documented historical-candle endpoint.
It deliberately does not create or refresh a SmartAPI session, inspect an
account, access price feeds, open a WebSocket, or submit/cancel any order.
The caller must supply a user-managed short-lived bearer token through local
environment configuration and invoke the application service manually.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
import os
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from algo_manus.domain.market_data import (
    Candle,
    CandleDataset,
    DataProvenance,
    DataSourceKind,
    DataUseCase,
)

ANGEL_HISTORICAL_CANDLE_URI = (
    "https://apiconnect.angelone.in/"
    "rest/secure/angelbroking/historical/v1/getCandleData"
)
_INTERVALS: dict[str, tuple[str, int]] = {
    "1m": ("ONE_MINUTE", 30),
    "3m": ("THREE_MINUTE", 60),
    "5m": ("FIVE_MINUTE", 100),
    "10m": ("TEN_MINUTE", 100),
    "15m": ("FIFTEEN_MINUTE", 200),
    "30m": ("THIRTY_MINUTE", 200),
    "1h": ("ONE_HOUR", 400),
    "1d": ("ONE_DAY", 2000),
}
_Transport = Callable[[str, bytes, dict[str, str]], bytes]


class AngelHistoricalCandleConfigurationError(ValueError):
    """Raised when the local read-only configuration is absent or incomplete."""


class AngelHistoricalCandleResponseError(ValueError):
    """Raised when Angel One returns a failed or malformed candle response."""


@dataclass(frozen=True, slots=True)
class AngelHistoricalCredentials:
    """Secret values supplied only by a user-managed local environment."""

    app_key: str
    mac_address: str

    def __post_init__(self) -> None:
        if not self.app_key.strip() or not self.mac_address.strip():
            raise AngelHistoricalCandleConfigurationError(
                "ALGO_MANUS_ANGEL_APP_KEY and ALGO_MANUS_ANGEL_MAC_ADDRESS are required"
            )


def _post_json(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
    """Perform one explicit adapter request to the fixed historical endpoint."""

    request = Request(uri, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=30) as response:  # noqa: S310 - approved fixed broker endpoint
        return response.read()


class AngelHistoricalCandleProvider:
    """Normalize documented Angel candles behind :class:`MarketDataProviderPort`.

    The adapter accepts an existing short-lived access token only.  It does not
    know client code, PIN, TOTP, refresh tokens, account endpoints or any order
    endpoint.  ``transport`` is injectable exclusively for deterministic tests.
    """

    source_name = "angel_one"
    source_kind = DataSourceKind.BROKER

    def __init__(
        self,
        *,
        credentials: AngelHistoricalCredentials | None,
        transport: _Transport | None = None,
        configuration_error: str | None = None,
        access_token: str | None = None,
    ) -> None:
        self._credentials = credentials
        self._transport = transport or _post_json
        self._configuration_error = configuration_error
        self._access_token = access_token.strip() if access_token else None

    @classmethod
    def from_environment(cls) -> "AngelHistoricalCandleProvider":
        """Load existing local-only values without exposing or persisting them."""

        app_key = os.environ.get("ALGO_MANUS_ANGEL_APP_KEY", "").strip()
        access_token = os.environ.get("ALGO_MANUS_ANGEL_ACCESS_TOKEN", "").strip()
        mac_address = os.environ.get("ALGO_MANUS_ANGEL_MAC_ADDRESS", "").strip()
        if not app_key and not access_token and not mac_address:
            return cls(credentials=None)
        if not app_key or not mac_address:
            return cls(
                credentials=None,
                configuration_error=(
                    "ALGO_MANUS_ANGEL_APP_KEY and ALGO_MANUS_ANGEL_MAC_ADDRESS "
                    "must be configured together"
                ),
            )
        return cls(
            credentials=AngelHistoricalCredentials(app_key, mac_address),
            access_token=access_token or None,
        )

    @property
    def credentials_configured(self) -> bool:
        return (
            self._credentials is not None
            and self._configuration_error is None
            and self._access_token is not None
        )

    @property
    def configuration_message(self) -> str:
        return self._configuration_error or (
            "ALGO_MANUS_ANGEL_APP_KEY and ALGO_MANUS_ANGEL_MAC_ADDRESS are required "
            if self._credentials is None
            else "an active local Angel session or ALGO_MANUS_ANGEL_ACCESS_TOKEN is required"
        )

    def set_access_token(self, access_token: str) -> None:
        """Accept a transient token from the local Option C session service only."""

        if not access_token.strip():
            raise ValueError("access token must not be blank")
        self._access_token = access_token

    def clear_access_token(self) -> None:
        """Discard any in-memory token handoff without an external request."""

        self._access_token = None

    def fetch_candles(
        self,
        *,
        instrument_id: str,
        interval: str,
        start: datetime,
        end: datetime,
        retrieved_at: datetime,
    ) -> CandleDataset:
        """Fetch one bounded, research-only historical-candle response."""

        if not self.credentials_configured:
            raise AngelHistoricalCandleConfigurationError(self.configuration_message)
        if start.tzinfo is None or end.tzinfo is None or retrieved_at.tzinfo is None:
            raise ValueError("historical-candle timestamps must be timezone-aware")
        if start >= end:
            raise ValueError("historical-candle start must be earlier than end")
        angel_interval, max_days = self._interval(interval)
        if end - start > timedelta(days=max_days):
            raise ValueError(
                f"Angel interval {interval} has a documented maximum span of {max_days} days"
            )
        exchange, token = self._parse_instrument_id(instrument_id)
        payload = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": angel_interval,
            "fromdate": self._format_bound(start),
            "todate": self._format_bound(end),
        }
        raw_content = self._transport(
            ANGEL_HISTORICAL_CANDLE_URI,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            self._headers(),
        )
        candles = self._parse_response(raw_content)
        return CandleDataset.create(
            instrument_id=instrument_id,
            interval=interval,
            provenance=DataProvenance(
                source_name=self.source_name,
                source_kind=self.source_kind,
                source_uri=ANGEL_HISTORICAL_CANDLE_URI,
                retrieved_at=retrieved_at,
                raw_content_sha256=sha256(raw_content).hexdigest(),
                adjustment_basis="unadjusted broker historical candles",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=candles,
        )

    def _headers(self) -> dict[str, str]:
        assert self._credentials is not None and self._access_token is not None
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-MACAddress": self._credentials.mac_address,
            "X-PrivateKey": self._credentials.app_key,
            "Authorization": f"Bearer {self._access_token}",
        }

    @staticmethod
    def _interval(interval: str) -> tuple[str, int]:
        try:
            return _INTERVALS[interval]
        except KeyError as exc:
            raise ValueError(f"unsupported Angel historical interval {interval!r}") from exc

    @staticmethod
    def _parse_instrument_id(instrument_id: str) -> tuple[str, str]:
        parts = instrument_id.split(":")
        if len(parts) != 4 or parts[0] != "ANGEL_ONE":
            raise ValueError("Angel historical data requires an ANGEL_ONE canonical instrument identity")
        exchange, segment, token = parts[1:]
        if exchange != segment or exchange not in {"NSE", "NFO", "BSE", "BFO", "MCX"} or not token:
            raise ValueError("Angel canonical instrument identity has an unsupported exchange or token")
        return exchange, token

    @staticmethod
    def _format_bound(value: datetime) -> str:
        return value.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _parse_response(raw_content: bytes) -> tuple[Candle, ...]:
        try:
            response = json.loads(raw_content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AngelHistoricalCandleResponseError(
                "Angel historical response must be UTF-8 JSON"
            ) from exc
        if not isinstance(response, dict):
            raise AngelHistoricalCandleResponseError("Angel historical response must be an object")
        if response.get("status") is not True:
            code = str(response.get("errorcode") or "unknown_error")
            message = str(response.get("message") or "unknown provider error")
            raise AngelHistoricalCandleResponseError(f"Angel historical request failed: {code}: {message}")
        records = response.get("data")
        if not isinstance(records, list) or not records:
            raise AngelHistoricalCandleResponseError(
                "Angel historical response must contain at least one candle record"
            )
        candles: list[Candle] = []
        for position, record in enumerate(records):
            if not isinstance(record, list) or len(record) != 6:
                raise AngelHistoricalCandleResponseError(
                    f"Angel historical candle {position} must contain six values"
                )
            timestamp, open_price, high_price, low_price, close_price, volume = record
            try:
                parsed_timestamp = datetime.fromisoformat(str(timestamp))
                candle = Candle(
                    timestamp=parsed_timestamp,
                    open=float(open_price),
                    high=float(high_price),
                    low=float(low_price),
                    close=float(close_price),
                    volume=float(volume),
                )
            except (TypeError, ValueError) as exc:
                raise AngelHistoricalCandleResponseError(
                    f"Angel historical candle {position} is malformed"
                ) from exc
            candles.append(candle)
        return tuple(candles)
