from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from algo_manus.domain.instruments import InstrumentStatus, InstrumentType, OptionType
from algo_manus.infrastructure.instruments.angel_one import (
    ANGEL_SCRIP_MASTER_URI,
    AngelScripMasterNormalizationError,
    AngelScripMasterProvider,
    _public_fetch,
)


class AngelScripMasterProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.downloaded_at = datetime(2026, 8, 25, 9, 15, tzinfo=timezone.utc)

    def test_normalizes_public_master_records_into_typed_snapshot(self) -> None:
        raw_content = json.dumps(
            [
                {
                    "token": "2885",
                    "symbol": "RELIANCE-EQ",
                    "name": "RELIANCE",
                    "expiry": "",
                    "strike": "-1.000000",
                    "lotsize": "1",
                    "instrumenttype": "",
                    "exch_seg": "NSE",
                    "tick_size": "5.000000",
                },
                {
                    "token": "46725",
                    "symbol": "NIFTY28AUG2625000CE",
                    "name": "NIFTY",
                    "expiry": "28AUG2026",
                    "strike": "2500000.000000",
                    "lotsize": "50",
                    "instrumenttype": "OPTIDX",
                    "exch_seg": "NFO",
                    "tick_size": "5.000000",
                },
                {
                    "token": "26000",
                    "symbol": "NIFTY 50",
                    "name": "NIFTY",
                    "expiry": "",
                    "strike": "0.000000",
                    "lotsize": "1",
                    "instrumenttype": "AMXIDX",
                    "exch_seg": "NSE",
                    "tick_size": "0.000000",
                },
                {
                    "token": "101",
                    "symbol": "USDINR",
                    "name": "USDINR",
                    "expiry": "",
                    "strike": "-1.000000",
                    "lotsize": "1",
                    "instrumenttype": "UNDCUR",
                    "exch_seg": "CDS",
                    "tick_size": "0.000000",
                },
                {
                    "token": "102",
                    "symbol": "MIBOR",
                    "name": "MIBOR reference",
                    "expiry": "",
                    "strike": "-1.000000",
                    "lotsize": "1",
                    "instrumenttype": "UNDIRT",
                    "exch_seg": "NFO",
                    "tick_size": "0.000000",
                },
                {
                    "token": "103",
                    "symbol": "NIFTY MIDCAP 50",
                    "name": "NIFTY MIDCAP 50",
                    "expiry": "",
                    "strike": "-1.000000",
                    "lotsize": "1",
                    "instrumenttype": "INDEX",
                    "exch_seg": "NSE",
                    "tick_size": "0.000000",
                },
                {
                    "token": "DHANIYA09OCT26CE11300FOCT26",
                    "symbol": "DHANIYA09OCT26CE11300FOCT26",
                    "name": "DHANIYA",
                    "expiry": "09OCT2026",
                    "strike": "1130000.000000",
                    "lotsize": "5",
                    "instrumenttype": "OPTFUT",
                    "exch_seg": "NCDEX",
                    "tick_size": "100.000000",
                },
                {
                    "token": "104",
                    "symbol": "GOLD",
                    "name": "GOLD underlying",
                    "expiry": "",
                    "strike": "-1.000000",
                    "lotsize": "1",
                    "instrumenttype": "UNDCOM",
                    "exch_seg": "NCDEX",
                    "tick_size": "0.000000",
                },
            ]
        ).encode("utf-8")
        provider = AngelScripMasterProvider(fetcher=lambda uri: raw_content)

        snapshot = provider.download_snapshot(downloaded_at=self.downloaded_at)

        self.assertEqual(provider.broker_name, "angel_one")
        self.assertEqual(snapshot.source_uri, ANGEL_SCRIP_MASTER_URI)
        self.assertEqual(len(snapshot.instruments), 8)
        (
            equity,
            option,
            index,
            currency,
            reference_index,
            source_index,
            commodity_option,
            commodity_underlier,
        ) = snapshot.instruments
        self.assertEqual(equity.instrument_id, "ANGEL_ONE:NSE:NSE:2885")
        self.assertEqual(equity.instrument_type, InstrumentType.EQUITY)
        self.assertEqual(equity.tick_size, 0.05)
        self.assertEqual(option.instrument_type, InstrumentType.OPTION)
        self.assertEqual(option.expiry.isoformat(), "2026-08-28")
        self.assertEqual(option.strike, 25000.0)
        self.assertEqual(option.option_type, OptionType.CALL)
        self.assertEqual(option.lot_size, 50)
        self.assertEqual(option.status, InstrumentStatus.ACTIVE)
        self.assertEqual(index.instrument_type, InstrumentType.INDEX)
        self.assertEqual(index.tick_size, None)
        self.assertEqual(currency.instrument_id, "ANGEL_ONE:CDS:CDS:101")
        self.assertEqual(currency.instrument_type, InstrumentType.CURRENCY)
        self.assertEqual(currency.expiry, None)
        self.assertEqual(reference_index.instrument_id, "ANGEL_ONE:NFO:NFO:102")
        self.assertEqual(reference_index.instrument_type, InstrumentType.INDEX)
        self.assertEqual(source_index.instrument_id, "ANGEL_ONE:NSE:NSE:103")
        self.assertEqual(source_index.instrument_type, InstrumentType.INDEX)
        self.assertEqual(commodity_option.instrument_id, "ANGEL_ONE:NCDEX:NCDEX:DHANIYA09OCT26CE11300FOCT26")
        self.assertEqual(commodity_option.instrument_type, InstrumentType.OPTION)
        self.assertEqual(commodity_option.option_type, OptionType.CALL)
        self.assertEqual(commodity_option.strike, 11300.0)
        self.assertEqual(commodity_underlier.instrument_id, "ANGEL_ONE:NCDEX:NCDEX:104")
        self.assertEqual(commodity_underlier.instrument_type, InstrumentType.COMMODITY)
        self.assertEqual(snapshot.content_sha256, __import__("hashlib").sha256(raw_content).hexdigest())

    def test_rejects_malformed_source_record_without_silent_substitution(self) -> None:
        raw_content = json.dumps(
            [{"token": "", "symbol": "", "exch_seg": "NSE"}]
        ).encode("utf-8")
        provider = AngelScripMasterProvider(fetcher=lambda uri: raw_content)

        with self.assertRaisesRegex(AngelScripMasterNormalizationError, "token"):
            provider.download_snapshot(downloaded_at=self.downloaded_at)

    def test_rejects_non_list_public_source_payload(self) -> None:
        provider = AngelScripMasterProvider(fetcher=lambda uri: b'{"status": "unexpected"}')

        with self.assertRaisesRegex(AngelScripMasterNormalizationError, "JSON list"):
            provider.download_snapshot(downloaded_at=self.downloaded_at)

    def test_resumes_a_truncated_public_transfer_using_the_same_fixed_source(self) -> None:
        first = _FakePublicResponse(chunks=[b"ab"], headers={"Content-Length": "4"})
        resumed = _FakePublicResponse(
            chunks=[b"cd"],
            headers={"Content-Range": "bytes 2-3/4"},
            status=206,
        )

        with patch(
            "algo_manus.infrastructure.instruments.angel_one.urlopen",
            side_effect=[first, resumed],
        ) as mocked_urlopen:
            content = _public_fetch(ANGEL_SCRIP_MASTER_URI)

        self.assertEqual(content, b"abcd")
        initial_request = mocked_urlopen.call_args_list[0].args[0]
        resumed_request = mocked_urlopen.call_args_list[1].args[0]
        self.assertIsNone(initial_request.get_header("Range"))
        self.assertEqual(resumed_request.get_header("Range"), "bytes=2-")


class _FakePublicResponse:
    def __init__(
        self,
        *,
        chunks: list[bytes],
        headers: dict[str, str],
        status: int = 200,
    ) -> None:
        self._chunks = iter(chunks)
        self.headers = headers
        self.status = status

    def __enter__(self) -> "_FakePublicResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, _: int) -> bytes:
        return next(self._chunks, b"")


if __name__ == "__main__":
    unittest.main()
