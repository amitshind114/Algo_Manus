from __future__ import annotations

from datetime import datetime, timezone
import inspect
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from algo_manus.domain.instruments import (
    Instrument,
    InstrumentMasterSnapshot,
    InstrumentType,
)
from algo_manus.infrastructure.instruments.sqlite_repository import (
    SqliteInstrumentSnapshotRepository,
)
from algo_manus.ui import runtime, workbench


class WorkbenchP2WiringTests(unittest.TestCase):
    def test_composition_root_mounts_shared_runtime_and_dhan_panel(self) -> None:
        source = inspect.getsource(workbench.run_workbench)
        page_source = inspect.getsource(workbench._data_and_instruments)
        self.assertIn("shared_local_dhan_historical_panel", source)
        self.assertIn("render_sidebar_navigation", source)
        self.assertIn("initialize_workbench_state", source)
        self.assertIn("dhan_historical_panel", page_source)
        self.assertIn("_dhan_historical_panel", page_source)

    def test_runtime_returns_no_dhan_panel_without_retained_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(os.environ, {"ALGO_MANUS_DATA_DIR": temp_dir}):
                st = SimpleNamespace(session_state={})
                self.assertIsNone(runtime.local_dhan_historical_panel(st))
                self.assertNotIn("dhan_historical_panel", st.session_state)

    def test_runtime_builds_panel_from_latest_dhan_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(os.environ, {"ALGO_MANUS_DATA_DIR": temp_dir}):
                repository = SqliteInstrumentSnapshotRepository(
                    Path(temp_dir) / "instrument_master.sqlite3"
                )
                snapshot = InstrumentMasterSnapshot.create(
                    broker="dhan",
                    source_uri="fixture://dhan/master",
                    raw_content=b"dhan-master-v1",
                    downloaded_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
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
                repository.save(snapshot)
                st = SimpleNamespace(session_state={})

                panel = runtime.local_dhan_historical_panel(st)

                self.assertIsNotNone(panel)
                assert panel is not None
                self.assertEqual(
                    [item.instrument_id for item in panel.active_instruments],
                    ["DHAN:NSE:NSE_EQ:1333"],
                )
                self.assertEqual(
                    st.session_state["dhan_historical_panel"].instrument_snapshot_id,
                    snapshot.snapshot_id,
                )


if __name__ == "__main__":
    unittest.main()
