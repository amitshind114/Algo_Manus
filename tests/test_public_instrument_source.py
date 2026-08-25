from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from algo_manus.application.public_instrument_source import PublicInstrumentSourceService
from algo_manus.infrastructure.instruments.angel_one import AngelScripMasterProvider
from algo_manus.infrastructure.instruments.sqlite_repository import (
    SqliteInstrumentSnapshotRepository,
)


class PublicInstrumentSourceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = SqliteInstrumentSnapshotRepository(
            Path(self.temp_dir.name) / "instrument_master.sqlite3"
        )
        raw_master = json.dumps(
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
                }
            ]
        ).encode("utf-8")
        self.provider = AngelScripMasterProvider(fetcher=lambda uri: raw_master)
        self.service = PublicInstrumentSourceService(self.repository, self.provider)
        self.now = datetime(2026, 8, 25, 9, 15, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_status_is_unavailable_until_user_invokes_manual_sync(self) -> None:
        status = self.service.status()

        self.assertEqual(status.broker_name, "angel_one")
        self.assertEqual(status.availability, "not_downloaded")
        self.assertIsNone(status.snapshot_id)
        self.assertTrue(status.manual_sync_required)

    def test_manual_sync_persists_immutable_snapshot_and_updates_status(self) -> None:
        result = self.service.sync(now=self.now)
        status = self.service.status()

        self.assertTrue(result.downloaded)
        self.assertEqual(result.reason, "downloaded_new_snapshot")
        self.assertEqual(status.availability, "available")
        self.assertEqual(status.snapshot_id, result.snapshot.snapshot_id)
        self.assertEqual(status.instrument_count, 1)
        self.assertEqual(status.last_checked_at, self.now)
        self.assertFalse(status.manual_sync_required)


if __name__ == "__main__":
    unittest.main()
