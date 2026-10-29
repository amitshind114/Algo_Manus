from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import tempfile
import unittest
from pathlib import Path

from algo_manus.application.public_instrument_source import PublicInstrumentSourceService
from algo_manus.domain.instruments import InstrumentType, OptionType
from algo_manus.infrastructure.instruments.dhan import (
    DHAN_INSTRUMENT_MASTER_URI,
    DhanInstrumentMasterNormalizationError,
    DhanInstrumentMasterProvider,
)
from algo_manus.infrastructure.instruments.sqlite_repository import (
    SqliteInstrumentSnapshotRepository,
)


_COLUMNS = [
    "EXCH_ID",
    "SEGMENT",
    "SECURITY_ID",
    "ISIN",
    "INSTRUMENT",
    "UNDERLYING_SECURITY_ID",
    "UNDERLYING_SYMBOL",
    "SYMBOL_NAME",
    "DISPLAY_NAME",
    "INSTRUMENT_TYPE",
    "SERIES",
    "LOT_SIZE",
    "SM_EXPIRY_DATE",
    "STRIKE_PRICE",
    "OPTION_TYPE",
    "TICK_SIZE",
]


def _csv(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "EXCH_ID": "NSE",
        "SEGMENT": "E",
        "SECURITY_ID": "1333",
        "ISIN": "INE002A01018",
        "INSTRUMENT": "EQUITY",
        "UNDERLYING_SECURITY_ID": "",
        "UNDERLYING_SYMBOL": "",
        "SYMBOL_NAME": "RELIANCE",
        "DISPLAY_NAME": "Reliance Industries",
        "INSTRUMENT_TYPE": "ES",
        "SERIES": "EQ",
        "LOT_SIZE": "1.0",
        "SM_EXPIRY_DATE": "",
        "STRIKE_PRICE": "",
        "OPTION_TYPE": "",
        "TICK_SIZE": "0.05",
    }
    row.update(overrides)
    return row


class DhanInstrumentMasterProviderTests(unittest.TestCase):
    downloaded_at = datetime(2026, 10, 29, 9, 15, tzinfo=timezone.utc)

    def test_normalizes_equity_derivative_and_index_records(self) -> None:
        raw_content = _csv(
            [
                _row(),
                _row(
                    SEGMENT="D",
                    SECURITY_ID="999001",
                    INSTRUMENT="OPTSTK",
                    INSTRUMENT_TYPE="OPTSTK",
                    SYMBOL_NAME="RELIANCE-26-OCT-2500-CE",
                    DISPLAY_NAME="RELIANCE 2500 CALL",
                    SERIES="NA",
                    LOT_SIZE="250.0",
                    SM_EXPIRY_DATE="2026-10-29",
                    STRIKE_PRICE="2500.00000",
                    OPTION_TYPE="CE",
                    TICK_SIZE="0.05",
                ),
                _row(
                    SEGMENT="D",
                    SECURITY_ID="999002",
                    INSTRUMENT="FUTSTK",
                    INSTRUMENT_TYPE="FUTSTK",
                    SYMBOL_NAME="RELIANCE-26-OCT-FUT",
                    DISPLAY_NAME="RELIANCE FUTURE",
                    SERIES="NA",
                    LOT_SIZE="250.0",
                    SM_EXPIRY_DATE="2026-10-29",
                    STRIKE_PRICE="-0.01000",
                    OPTION_TYPE="XX",
                    TICK_SIZE="0.05",
                ),
                _row(
                    SEGMENT="I",
                    SECURITY_ID="13",
                    INSTRUMENT="INDEX",
                    INSTRUMENT_TYPE="INDEX",
                    SYMBOL_NAME="NIFTY 50",
                    DISPLAY_NAME="NIFTY 50",
                    SERIES="NA",
                    LOT_SIZE="1.0",
                    STRIKE_PRICE="-0.01000",
                    OPTION_TYPE="XX",
                    TICK_SIZE="0.05",
                ),
            ]
        )
        provider = DhanInstrumentMasterProvider(fetcher=lambda uri: raw_content)

        snapshot = provider.download_snapshot(downloaded_at=self.downloaded_at)

        self.assertEqual(provider.broker_name, "dhan")
        self.assertEqual(snapshot.source_uri, DHAN_INSTRUMENT_MASTER_URI)
        self.assertEqual(len(snapshot.instruments), 4)
        equity, option, future, index = snapshot.instruments
        self.assertEqual(equity.instrument_id, "DHAN:NSE:NSE_EQ:1333")
        self.assertEqual(equity.instrument_type, InstrumentType.EQUITY)
        self.assertEqual(option.instrument_id, "DHAN:NSE:NSE_FNO:999001")
        self.assertEqual(option.instrument_type, InstrumentType.OPTION)
        self.assertEqual(option.option_type, OptionType.CALL)
        self.assertEqual(option.strike, 2500.0)
        self.assertEqual(future.instrument_type, InstrumentType.FUTURE)
        self.assertEqual(index.instrument_id, "DHAN:NSE:IDX_I:13")
        self.assertEqual(index.instrument_type, InstrumentType.INDEX)

    def test_normalizes_currency_and_commodity_derivative_segments(self) -> None:
        raw_content = _csv(
            [
                _row(
                    EXCH_ID="BSE",
                    SEGMENT="C",
                    SECURITY_ID="700001",
                    INSTRUMENT="FUTCUR",
                    INSTRUMENT_TYPE="FUTCUR",
                    SYMBOL_NAME="USDINR FUT",
                    DISPLAY_NAME="USDINR FUT",
                    SERIES="NA",
                    LOT_SIZE="1.0",
                    SM_EXPIRY_DATE="2026-11-26",
                    STRIKE_PRICE="-0.01000",
                    OPTION_TYPE="XX",
                    TICK_SIZE="0.25",
                ),
                _row(
                    EXCH_ID="MCX",
                    SEGMENT="M",
                    SECURITY_ID="800001",
                    INSTRUMENT="FUTCOM",
                    INSTRUMENT_TYPE="FUTCOM",
                    SYMBOL_NAME="GOLD FUT",
                    DISPLAY_NAME="GOLD FUT",
                    SERIES="NA",
                    LOT_SIZE="100.0",
                    SM_EXPIRY_DATE="2026-11-05",
                    STRIKE_PRICE="-0.01000",
                    OPTION_TYPE="XX",
                    TICK_SIZE="1.0",
                ),
            ]
        )
        snapshot = DhanInstrumentMasterProvider(
            fetcher=lambda uri: raw_content
        ).download_snapshot(downloaded_at=self.downloaded_at)

        self.assertEqual(snapshot.instruments[0].segment, "BSE_CURRENCY")
        self.assertEqual(snapshot.instruments[1].segment, "MCX_COMM")
        self.assertEqual(snapshot.instruments[1].instrument_type, InstrumentType.FUTURE)

    def test_rejects_missing_columns_and_malformed_records(self) -> None:
        missing_columns = b"EXCH_ID,SEGMENT\nNSE,E\n"
        with self.assertRaisesRegex(DhanInstrumentMasterNormalizationError, "missing columns"):
            DhanInstrumentMasterProvider(fetcher=lambda uri: missing_columns).download_snapshot(
                downloaded_at=self.downloaded_at
            )

        malformed = _csv([_row(SECURITY_ID="", SYMBOL_NAME="RELIANCE")])
        with self.assertRaisesRegex(DhanInstrumentMasterNormalizationError, "SECURITY_ID"):
            DhanInstrumentMasterProvider(fetcher=lambda uri: malformed).download_snapshot(
                downloaded_at=self.downloaded_at
            )

    def test_rejects_ambiguous_option_and_duplicate_identity_records(self) -> None:
        malformed_option = _csv(
            [
                _row(
                    SEGMENT="D",
                    INSTRUMENT="OPTSTK",
                    INSTRUMENT_TYPE="OPTSTK",
                    SM_EXPIRY_DATE="2026-10-29",
                    STRIKE_PRICE="2500",
                    OPTION_TYPE="XX",
                    LOT_SIZE="250",
                    TICK_SIZE="0.05",
                )
            ]
        )
        with self.assertRaisesRegex(DhanInstrumentMasterNormalizationError, "option type"):
            DhanInstrumentMasterProvider(fetcher=lambda uri: malformed_option).download_snapshot(
                downloaded_at=self.downloaded_at
            )

        duplicate = _csv([_row(), _row(DISPLAY_NAME="Same token, different label")])
        with self.assertRaisesRegex(DhanInstrumentMasterNormalizationError, "duplicate"):
            DhanInstrumentMasterProvider(fetcher=lambda uri: duplicate).download_snapshot(
                downloaded_at=self.downloaded_at
            )


class DhanInstrumentMasterWorkflowTests(unittest.TestCase):
    def test_manual_sync_persists_immutable_snapshot_and_reuses_same_content(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        repository = SqliteInstrumentSnapshotRepository(
            Path(temp_dir.name) / "instrument_master.sqlite3"
        )
        raw_content = _csv([_row()])
        provider = DhanInstrumentMasterProvider(fetcher=lambda uri: raw_content)
        service = PublicInstrumentSourceService(repository, provider)
        now = datetime(2026, 10, 29, 9, 15, tzinfo=timezone.utc)

        first = service.sync(now=now)
        second = service.sync(now=now.replace(minute=16))
        loaded = repository.get(first.snapshot.snapshot_id)

        self.assertTrue(first.downloaded)
        self.assertEqual(first.reason, "downloaded_new_snapshot")
        self.assertFalse(second.downloaded)
        self.assertEqual(second.reason, "unchanged_content")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.content_sha256, first.snapshot.content_sha256)
        self.assertEqual(loaded.instruments[0].broker, "dhan")
        self.assertEqual(len(loaded.instruments), 1)
        self.assertEqual(repository.latest("dhan").snapshot_id, first.snapshot.snapshot_id)
        self.assertEqual(repository.last_checked_at("dhan"), now.replace(minute=16))


if __name__ == "__main__":
    unittest.main()
