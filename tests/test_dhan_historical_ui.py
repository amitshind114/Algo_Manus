from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import tempfile
from pathlib import Path
import unittest

from algo_manus.domain.instruments import Instrument, InstrumentMasterSnapshot, InstrumentType
from algo_manus.infrastructure.market_data.dhan_historical import DhanHistoricalCandleProvider
from algo_manus.infrastructure.market_data.sqlite_repository import SqliteCandleDatasetRepository
from algo_manus.ui.dhan_historical import (
    DhanInstrumentSelectionError,
    DhanHistoricalPanel,
    DhanRetrievalForm,
    SUPPORTED_INTERVALS,
)


class DhanHistoricalPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "dhan_datasets.sqlite3"
        self.start = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)
        self.end = self.start + timedelta(days=5)
        self.retrieved_at = self.end + timedelta(hours=1)
        self.payload = {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000, 1100],
            "timestamp": [
                int(self.start.timestamp()),
                int(self.start.timestamp()) + 300,
            ],
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _panel(self) -> DhanHistoricalPanel:
        encoded = json.dumps(self.payload).encode("utf-8")

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            return encoded

        provider = DhanHistoricalCandleProvider(
            credentials=type("Credentials", (), {"access_token": "test-token"})(),
            transport=transport,
        )
        repository = SqliteCandleDatasetRepository(self.database_path)
        snapshot = InstrumentMasterSnapshot.create(
            broker="dhan",
            source_uri="fixture://dhan/instrument-master",
            raw_content=b"dhan-master-v1",
            downloaded_at=self.retrieved_at,
            instruments=(
                Instrument(
                    broker="dhan",
                    exchange="NSE",
                    segment="NSE_EQ",
                    broker_token="1333",
                    trading_symbol="RELIANCE",
                    display_name="Reliance Industries",
                    instrument_type=InstrumentType.EQUITY,
                ),
            ),
        )
        return DhanHistoricalPanel(
            provider=provider,
            repository=repository,
            instrument_snapshot=snapshot,
        )

    def _form(self) -> DhanRetrievalForm:
        return DhanRetrievalForm(
            instrument_id="DHAN:NSE:NSE_EQ:1333",
            interval="5m",
            start=self.start,
            end=self.end,
        )

    def test_supported_intervals_match_dhan_contract(self) -> None:
        self.assertEqual(
            SUPPORTED_INTERVALS,
            ("1d", "1m", "5m", "15m", "25m", "60m"),
        )

    def test_panel_reports_configured_provider(self) -> None:
        panel = self._panel()
        self.assertEqual(panel.configuration_status, "configured")

    def test_retrieve_persists_research_dataset_and_returns_safe_metadata(self) -> None:
        panel = self._panel()
        result = panel.retrieve(self._form(), retrieved_at=self.retrieved_at)

        self.assertEqual(result["instrument_id"], "DHAN:NSE:NSE_EQ:1333")
        self.assertEqual(result["source_name"], "dhan")
        self.assertEqual(result["source_kind"], "BROKER")
        self.assertEqual(result["use_case"], "RESEARCH")
        self.assertEqual(result["candle_count"], 2)
        self.assertEqual(result["first_candle"], self.start)
        self.assertNotIn("access_token", result)
        self.assertNotIn("raw_response", result)

    def test_allows_intraday_window_over_ninety_days_for_provider_chunking(self) -> None:
        form = DhanRetrievalForm(
            instrument_id="DHAN:NSE:NSE_EQ:1333",
            interval="5m",
            start=self.start,
            end=self.start + timedelta(days=91),
        )
        self.assertEqual(form.end - form.start, timedelta(days=91))

    def test_rejects_intraday_window_over_five_years(self) -> None:
        with self.assertRaisesRegex(ValueError, "limited to five years"):
            DhanRetrievalForm(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=self.start,
                end=self.start + timedelta(days=365 * 5 + 3),
            )

    def test_rejects_unsupported_interval(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported Dhan historical interval"):
            DhanRetrievalForm(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="3m",
                start=self.start,
                end=self.end,
            )

    def test_rejects_naive_timestamps(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            DhanRetrievalForm(
                instrument_id="DHAN:NSE_EQ:1333",
                interval="5m",
                start=datetime(2026, 8, 3),
                end=datetime(2026, 8, 8),
            )

    def test_rejects_instrument_not_in_selected_snapshot(self) -> None:
        panel = self._panel()
        with self.assertRaises(DhanInstrumentSelectionError):
            panel.retrieve(
                DhanRetrievalForm(
                    instrument_id="DHAN:NSE:NSE_EQ:9999",
                    interval="5m",
                    start=self.start,
                    end=self.end,
                ),
                retrieved_at=self.retrieved_at,
            )


if __name__ == "__main__":
    unittest.main()
