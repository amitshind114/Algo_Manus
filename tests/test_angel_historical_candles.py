from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import unittest

from algo_manus.application.market_data import MarketDataRequest
from algo_manus.domain.market_data import DataUseCase
from algo_manus.infrastructure.market_data.angel_one import (
    ANGEL_HISTORICAL_CANDLE_URI,
    AngelHistoricalCandleConfigurationError,
    AngelHistoricalCandleProvider,
    AngelHistoricalCandleResponseError,
    AngelHistoricalCredentials,
)


class AngelHistoricalCandleProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 8, 20, 9, 15, tzinfo=timezone.utc)
        self.end = datetime(2026, 8, 21, 9, 15, tzinfo=timezone.utc)

    def _request(self, *, interval: str = "1d") -> MarketDataRequest:
        return MarketDataRequest(
            instrument_id="ANGEL_ONE:NSE:NSE:500325",
            interval=interval,
            start=self.start,
            end=self.end,
            use_case=DataUseCase.RESEARCH,
        )

    def _provider(self, transport):
        return AngelHistoricalCandleProvider(
            credentials=AngelHistoricalCredentials(
                app_key="fixture-app-key",
                access_token="fixture-access-token",
                mac_address="00:11:22:33:44:55",
            ),
            transport=transport,
        )

    def test_normalizes_a_documented_read_only_candle_response(self) -> None:
        captured: dict[str, object] = {}

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            captured.update(uri=uri, body=json.loads(body), headers=headers)
            return json.dumps(
                {
                    "status": True,
                    "message": "SUCCESS",
                    "errorcode": "",
                    "data": [
                        ["2026-08-20T09:15:00+05:30", 101, 104, 100, 103, 1200],
                        ["2026-08-20T09:16:00+05:30", 103, 105, 102, 104, 900],
                    ],
                }
            ).encode()

        dataset = self._provider(transport).fetch_candles(
            instrument_id=self._request().instrument_id,
            interval="1m",
            start=self.start,
            end=self.end,
            retrieved_at=self.end,
        )

        self.assertEqual(captured["uri"], ANGEL_HISTORICAL_CANDLE_URI)
        self.assertEqual(
            captured["body"],
            {
                "exchange": "NSE",
                "symboltoken": "500325",
                "interval": "ONE_MINUTE",
                "fromdate": "2026-08-20 14:45",
                "todate": "2026-08-21 14:45",
            },
        )
        self.assertEqual(captured["headers"]["Authorization"], "Bearer fixture-access-token")
        self.assertEqual(captured["headers"]["X-PrivateKey"], "fixture-app-key")
        self.assertEqual(captured["headers"]["X-MACAddress"], "00:11:22:33:44:55")
        self.assertEqual(dataset.instrument_id, "ANGEL_ONE:NSE:NSE:500325")
        self.assertEqual(dataset.interval, "1m")
        self.assertEqual(dataset.candles[0].timestamp.utcoffset(), timedelta(hours=5, minutes=30))
        self.assertEqual(dataset.provenance.use_case, DataUseCase.RESEARCH)

    def test_rejects_missing_local_credentials_before_transport(self) -> None:
        calls = 0

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            nonlocal calls
            calls += 1
            return b"{}"

        provider = AngelHistoricalCandleProvider(credentials=None, transport=transport)

        with self.assertRaisesRegex(AngelHistoricalCandleConfigurationError, "ALGO_MANUS_ANGEL"):
            provider.fetch_candles(
                instrument_id=self._request().instrument_id,
                interval="1d",
                start=self.start,
                end=self.end,
                retrieved_at=self.end,
            )

        self.assertEqual(calls, 0)

    def test_rejects_requests_above_the_documented_interval_limit_before_transport(self) -> None:
        calls = 0

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            nonlocal calls
            calls += 1
            return b"{}"

        provider = self._provider(transport)

        with self.assertRaisesRegex(ValueError, "maximum span"):
            provider.fetch_candles(
                instrument_id=self._request().instrument_id,
                interval="1m",
                start=self.start,
                end=self.start + timedelta(days=31),
                retrieved_at=self.end,
            )

        self.assertEqual(calls, 0)

    def test_rejects_a_failed_or_malformed_provider_response(self) -> None:
        def rejected(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            return json.dumps(
                {"status": False, "message": "Token expired", "errorcode": "AG8002", "data": None}
            ).encode()

        with self.assertRaisesRegex(AngelHistoricalCandleResponseError, "AG8002"):
            self._provider(rejected).fetch_candles(
                instrument_id=self._request().instrument_id,
                interval="1d",
                start=self.start,
                end=self.end,
                retrieved_at=self.end,
            )


if __name__ == "__main__":
    unittest.main()
