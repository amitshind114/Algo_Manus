from __future__ import annotations

from datetime import datetime, timezone
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from algo_manus.ui.navigation import (
    DEFAULT_PAGE,
    NAV_ITEMS,
    normalize_page,
    valid_pages,
)
from algo_manus.ui.runtime import (
    initialize_workbench_state,
    local_data_root,
)
from algo_manus.ui.theme import apply_workbench_style, render_header


class NavigationTests(unittest.TestCase):
    def test_navigation_items_are_stable(self) -> None:
        self.assertEqual(
            NAV_ITEMS,
            (
                ("Home", "Overview"),
                ("Data & instruments", "Data & instruments"),
                ("Backtesting", "Backtesting"),
                ("Multi-test leaderboard", "Multi-test leaderboard"),
                ("Strategies", "Strategies"),
                ("Reporting", "Reporting"),
                ("Risk & paper", "Risk & paper"),
            ),
        )

    def test_valid_pages_match_navigation(self) -> None:
        self.assertEqual(valid_pages(), {page for _, page in NAV_ITEMS})

    def test_normalize_page_accepts_valid_page(self) -> None:
        self.assertEqual(normalize_page("Backtesting"), "Backtesting")

    def test_normalize_page_falls_back_to_default(self) -> None:
        self.assertEqual(normalize_page("Unknown"), DEFAULT_PAGE)
        self.assertEqual(normalize_page(None), DEFAULT_PAGE)


class RuntimeStateTests(unittest.TestCase):
    def test_local_data_root_uses_environment_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(os.environ, {"ALGO_MANUS_DATA_DIR": temp_dir}):
                self.assertEqual(local_data_root(), Path(temp_dir))

    def test_local_data_root_defaults_to_home(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ALGO_MANUS_DATA_DIR", None)
            self.assertEqual(local_data_root(), Path.home() / ".algo-manus")

    def test_initialize_state_uses_defaults(self) -> None:
        st = SimpleNamespace(session_state={})
        batch = SimpleNamespace(batch_id="batch-1")
        initialize_workbench_state(
            st,
            instrument_ids=("INS-1", "INS-2", "INS-3", "INS-4"),
            persisted_history=[batch],
        )

        self.assertEqual(st.session_state["selected_ids"], ("INS-1", "INS-2", "INS-3"))
        self.assertEqual(st.session_state["history"], [batch])
        self.assertEqual(st.session_state["active_batch"], batch)
        self.assertEqual(st.session_state["workspace"], DEFAULT_PAGE)

    def test_initialize_state_resets_invalid_workspace(self) -> None:
        st = SimpleNamespace(session_state={"workspace": "Unknown"})
        initialize_workbench_state(
            st,
            instrument_ids=("INS-1",),
            persisted_history=[],
        )

        self.assertEqual(st.session_state["workspace"], DEFAULT_PAGE)

    def test_initialize_state_preserves_active_batch(self) -> None:
        batch = SimpleNamespace(batch_id="batch-1")
        st = SimpleNamespace(
            session_state={
                "active_batch": batch,
                "workspace": "Backtesting",
            }
        )
        initialize_workbench_state(
            st,
            instrument_ids=("INS-1",),
            persisted_history=[batch],
        )

        self.assertEqual(st.session_state["active_batch"], batch)
        self.assertEqual(st.session_state["workspace"], "Backtesting")


class ThemeTests(unittest.TestCase):
    def test_style_and_header_use_streamlit_contract(self) -> None:
        calls = []

        def mark(*args, **kwargs):
            calls.append(("markdown", args, kwargs))

        def caption(*args, **kwargs):
            calls.append(("caption", args, kwargs))

        st = SimpleNamespace(markdown=mark, caption=caption)
        apply_workbench_style(st)
        render_header(st, "Title", "Subtitle")

        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[1][1][0], "Title")
        self.assertEqual(calls[2][0], "caption")
        self.assertEqual(calls[2][1][0], "Subtitle")


if __name__ == "__main__":
    unittest.main()
