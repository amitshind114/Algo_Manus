from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from algo_manus.domain.market_data import DataSourceKind, DataUseCase
from algo_manus.infrastructure.market_data.dhan_client import (
    DHAN_DAILY_CANDLE_URI,
    DHAN_INTRADAY_CANDLE_URI,
    DhanRateLimitTransportError,
    DhanTransportError,
)
from algo_manus.infrastructure.market_data.dhan_historical import (
    DhanHistoricalCandleProvider,
    DhanHistoricalConfigurationError,
    DhanHistoricalInstrumentError,
    DhanHistoricalIntervalError,
    DhanHistoricalRateLimitError,
    DhanHistoricalRequestError,
    DhanHistoricalResponseError,
)


class DhanHistoricalCandleProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)
        self.end = self.start + timedelta(days=5)
        self.retrieved_at = self.end + timedelta(hours=1)
        self.credentials = type(
            "Credentials", (), {"access_token": "test-token"}
        )()

    def _transport(self, payload: dict | list | str | bytes):
        encoded = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )
        calls: list[tuple[str, bytes, dict[str, str]]] = []

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            calls.append((uri, body, headers))
            return encoded

        transport.calls = calls  # type: ignore[attr-defined]
        return transport

    def _provider(self, payload: dict | list | str | bytes):
        transport = self._transport(payload)
        provider = DhanHistoricalCandleProvider(
            credentials=self.credentials,
            transport=transport,
        )
        return provider, transport

    def _sequence_provider(self, payloads: list[dict]):
        encoded_payloads = [json.dumps(payload).encode("utf-8") for payload in payloads]
        calls: list[tuple[str, bytes, dict[str, str]]] = []

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            calls.append((uri, body, headers))
            return encoded_payloads[len(calls) - 1]

        transport.calls = calls  # type: ignore[attr-defined]
        return (
            DhanHistoricalCandleProvider(
                credentials=self.credentials,
                transport=transport,
            ),
            transport,
            encoded_payloads,
        )

    def _valid_payload(self) -> dict:
        base = int(self.start.timestamp())
        return {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000, 1100],
            "timestamp": [base, base + 300],
        }

    def test_normalizes_documented_intraday_response(self) -> None:
        provider, transport = self._provider(self._valid_payload())
        dataset = provider.fetch_candles(
            instrument_id="DHAN:NSE_EQ:1333",
            interval="5m",
            start=self.start,
            end=self.end,
            retrieved_at=self.retrieved_at,
        )

        self.assertEqual(len(transport.calls), 1)
        uri, body, headers = transport.calls[0]
        self.assertEqual(uri, DHAN_INTRADAY_CANDLE_URI)
        self.assertEqual(headers["access-token"], "test-token")
        request = json.loads(body)
        self.assertEqual(request["securityId"], "1333")
        self.assertEqual(request["exchangeSegment"], "NSE_EQ")
        self.assertEqual(request["instrument"], "EQUITY")
        self.assertEqual(request["interval"], 5)
        self.assertFalse(request["oi"])
        self.assertEqual(request["fromDate"], "2026-08-03 14:45:00")
        self.assertEqual(request["toDate"], "2026-08-08 14:45:00")
        self.assertEqual(dataset.provenance.source_name, "dhan")
        self.assertEqual(dataset.provenance.source_kind, DataSourceKind.BROKER)
        self.assertEqual(len(dataset.candles), 2)
        self.assertEqual(dataset.candles[0].timestamp, self.start)
        self.assertEqual(
            dataset.provenance.raw_content_sha256,
            sha256(json.dumps(self._valid_payload()).encode("utf-8")).hexdigest(),
        )
        self.assertEqual(dataset.provenance.use_case, DataUseCase.RESEARCH)

    def test_uses_daily_endpoint_for_daily_interval(self) -> None:
        provider, transport = self._provider(self._valid_payload())
        provider.fetch_candles(
            instrument_id="DHAN:NSE_EQ:1333",
            interval="1d",
            start=self.start,
            end=self.end,
            retrieved_at=self.retrieved_at,
        )

        uri, _, _ = transport.calls[0]
        self.assertEqual(uri, DHAN_DAILY_CANDLE_URI)

        request = json.loads(transport.calls[0][1])
        self.assertEqual(request["instrument"], "EQUITY")
        self.assertFalse(request["oi"])
        self.assertEqual(request["expiryCode"], 0)
        self.assertNotIn("interval", request)

    def test_missing_credentials_fail_before_transport(self) -> None:
        provider = DhanHistoricalCandleProvider(credentials=None)
        with self.assertRaises(DhanHistoricalConfigurationError):
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )

    def test_rejects_unsupported_interval(self) -> None:
        provider, transport = self._provider(self._valid_payload())
        with self.assertRaises(DhanHistoricalIntervalError):
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="3m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )
        self.assertEqual(transport.calls, [])

    def test_splits_long_intraday_window_into_sequential_ninety_day_chunks(self) -> None:
        first_payload = self._valid_payload()
        second_start = self.start + timedelta(days=90)
        second_payload = {
            "open": [110.0, 111.0],
            "high": [112.0, 113.0],
            "low": [109.0, 110.0],
            "close": [111.0, 112.0],
            "volume": [1200, 1300],
            "timestamp": [int(second_start.timestamp()), int(second_start.timestamp()) + 300],
        }
        provider, transport, encoded = self._sequence_provider(
            [first_payload, second_payload]
        )

        dataset = provider.fetch_candles(
            instrument_id="DHAN:NSE_EQ:1333",
            interval="5m",
            start=self.start,
            end=self.start + timedelta(days=95),
            retrieved_at=self.start + timedelta(days=96),
        )

        self.assertEqual(len(transport.calls), 2)
        first_request = json.loads(transport.calls[0][1])
        second_request = json.loads(transport.calls[1][1])
        self.assertEqual(first_request["fromDate"], "2026-08-03 14:45:00")
        self.assertEqual(first_request["toDate"], "2026-11-01 14:45:00")
        self.assertEqual(second_request["fromDate"], "2026-11-01 14:45:00")
        self.assertEqual(second_request["toDate"], "2026-11-06 14:45:00")
        self.assertEqual(len(dataset.candles), 4)
        self.assertEqual(
            dataset.provenance.raw_content_sha256,
            sha256(b"".join(encoded)).hexdigest(),
        )

    def test_rejects_overlapping_chunk_responses(self) -> None:
        first_payload = self._valid_payload()
        second_payload = self._valid_payload()
        provider, _, _ = self._sequence_provider([first_payload, second_payload])

        with self.assertRaisesRegex(DhanHistoricalResponseError, "overlap"):
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.start + timedelta(days=95),
                retrieved_at=self.start + timedelta(days=96),
            )

    def test_rejects_non_equity_segment_without_guessing_instrument_type(self) -> None:
        provider, transport = self._provider(self._valid_payload())
        with self.assertRaises(DhanHistoricalInstrumentError):
            provider.fetch_candles(
                instrument_id="DHAN:NSE_FNO:1333",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )
        self.assertEqual(transport.calls, [])

    def test_rejects_invalid_instrument_identity(self) -> None:
        provider, transport = self._provider(self._valid_payload())
        with self.assertRaises(DhanHistoricalInstrumentError):
            provider.fetch_candles(
                instrument_id="ANGEL_ONE:NSE:NSE:500325",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )
        self.assertEqual(transport.calls, [])

    def test_rejects_empty_response(self) -> None:
        payload = self._valid_payload()
        for field in payload:
            payload[field] = []
        provider, _ = self._provider(payload)
        with self.assertRaises(DhanHistoricalResponseError):
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )

    def test_rejects_duplicate_or_out_of_order_timestamps(self) -> None:
        payload = self._valid_payload()
        payload["timestamp"][1] = payload["timestamp"][0]
        provider, _ = self._provider(payload)
        with self.assertRaises(DhanHistoricalResponseError):
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )

    def test_rejects_inconsistent_ohlc(self) -> None:
        payload = self._valid_payload()
        payload["high"][0] = 90.0
        provider, _ = self._provider(payload)
        with self.assertRaises(DhanHistoricalResponseError):
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )

    def test_rejects_negative_volume(self) -> None:
        payload = self._valid_payload()
        payload["volume"][0] = -1
        provider, _ = self._provider(payload)
        with self.assertRaises(DhanHistoricalResponseError):
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )

    def test_normalizes_provider_rate_limit_error_without_response_body(self) -> None:
        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            raise DhanRateLimitTransportError("internal provider detail with token")

        provider = DhanHistoricalCandleProvider(
            credentials=self.credentials,
            transport=transport,
        )
        with self.assertRaisesRegex(DhanHistoricalRateLimitError, "retry manually") as raised:
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )
        self.assertNotIn("token", str(raised.exception))

    def test_normalizes_transport_error_without_secret_details(self) -> None:
        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            raise DhanTransportError("internal provider detail with token")

        provider = DhanHistoricalCandleProvider(
            credentials=self.credentials,
            transport=transport,
        )
        with self.assertRaises(DhanHistoricalRequestError) as raised:
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )
        self.assertNotIn("token", str(raised.exception))

    def test_normalizes_provider_error_code_without_raw_response(self) -> None:
        provider, _ = self._provider(
            {
                "status": False,
                "errorCode": "DH-905",
                "message": "token must not be shown",
            }
        )
        with self.assertRaisesRegex(DhanHistoricalRequestError, "DH-905") as raised:
            provider.fetch_candles(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.end,
                retrieved_at=self.retrieved_at,
            )
        self.assertNotIn("token must not be shown", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
