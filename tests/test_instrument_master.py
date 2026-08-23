from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from algo_manus.application.instrument_sync import (
    InstrumentMasterSyncService,
    ResearchUniverseService,
    SnapshotFreshnessPolicy,
)
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.infrastructure.instruments.sqlite_repository import SqliteInstrumentSnapshotRepository
from tests.fixtures import instrument, snapshot


class FixtureBrokerMaster:
    """A deterministic provider that proves the port without a network call."""

    broker_name = "angel_one"

    def __init__(self, fixture_snapshot, raw_content: bytes = b"fixture-master-v1"):
        self.fixture_snapshot = fixture_snapshot
        self.raw_content = raw_content
        self.calls = 0

    def download_snapshot(self, *, downloaded_at: datetime):
        self.calls += 1
        return snapshot(
            content=self.raw_content,
            downloaded_at=downloaded_at,
            instruments=self.fixture_snapshot.instruments,
        )


class InstrumentMasterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = SqliteInstrumentSnapshotRepository(
            Path(self.temp_dir.name) / "instrument_master.sqlite3"
        )
        self.now = datetime(2026, 8, 23, 9, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_snapshot_is_immutable_and_preserves_identity(self) -> None:
        master = snapshot(downloaded_at=self.now)
        self.repository.save(master)

        loaded = self.repository.get(master.snapshot_id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.content_sha256, master.content_sha256)
        self.assertEqual(loaded.instruments[0].instrument_id, "ANGEL_ONE:NSE:NSE:500325")
        self.assertEqual(len(loaded.active_instruments), 2)

    def test_stale_snapshot_downloads_once_then_reuses_unchanged_content(self) -> None:
        prior = snapshot(downloaded_at=self.now - timedelta(days=2))
        self.repository.save(prior)
        provider = FixtureBrokerMaster(snapshot(content=b"new-master"), raw_content=b"new-master")
        service = InstrumentMasterSyncService(
            self.repository,
            SnapshotFreshnessPolicy(max_age=timedelta(hours=24)),
        )

        first = service.sync_if_stale(provider, now=self.now)
        second = service.sync_if_stale(provider, now=self.now + timedelta(minutes=1))

        self.assertTrue(first.downloaded)
        self.assertEqual(first.reason, "downloaded_new_snapshot")
        self.assertFalse(second.downloaded)
        self.assertEqual(second.reason, "fresh_snapshot")
        self.assertEqual(provider.calls, 1)

    def test_unchanged_stale_master_records_check_without_redownloading(self) -> None:
        prior = snapshot(downloaded_at=self.now - timedelta(days=2))
        self.repository.save(prior)
        provider = FixtureBrokerMaster(prior, raw_content=b"fixture-master-v1")
        service = InstrumentMasterSyncService(
            self.repository,
            SnapshotFreshnessPolicy(max_age=timedelta(hours=24)),
        )

        first = service.sync_if_stale(provider, now=self.now)
        second = service.sync_if_stale(provider, now=self.now + timedelta(minutes=1))

        self.assertFalse(first.downloaded)
        self.assertEqual(first.reason, "unchanged_content")
        self.assertFalse(second.downloaded)
        self.assertEqual(second.reason, "fresh_snapshot")
        self.assertEqual(provider.calls, 1)

    def test_universe_blocks_inactive_or_unknown_instruments(self) -> None:
        inactive = instrument(
            token="532540",
            symbol="TCS-EQ",
            display_name="TATA CONSULTANCY",
            status=InstrumentStatus.INACTIVE,
        )
        master = snapshot(instruments=(
            instrument(token="500325", symbol="RELIANCE-EQ", display_name="RELIANCE INDUSTRIES"),
            inactive,
        ))
        service = ResearchUniverseService()

        universe = service.create(
            universe_id="core-equities",
            name="Core equities",
            snapshot=master,
            selected_instrument_ids=("ANGEL_ONE:NSE:NSE:500325",),
        )
        self.assertEqual(universe.snapshot_id, master.snapshot_id)

        with self.assertRaisesRegex(ValueError, "not active"):
            service.create(
                universe_id="inactive",
                name="Inactive",
                snapshot=master,
                selected_instrument_ids=("ANGEL_ONE:NSE:NSE:532540",),
            )

        with self.assertRaisesRegex(ValueError, "absent"):
            service.create(
                universe_id="unknown",
                name="Unknown",
                snapshot=master,
                selected_instrument_ids=("ANGEL_ONE:NSE:NSE:999999",),
            )


if __name__ == "__main__":
    unittest.main()
