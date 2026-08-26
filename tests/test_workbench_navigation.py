"""Workbench navigation contract for the current research-and-paper interface."""

from __future__ import annotations

import unittest

from algo_manus.ui.workbench import NAV_ITEMS


class WorkbenchNavigationTests(unittest.TestCase):
    def test_navigation_exposes_current_operational_workspaces_without_legacy_roadmap(self) -> None:
        pages = tuple(page for _, page in NAV_ITEMS)

        self.assertEqual(
            pages,
            (
                "Overview",
                "Data & instruments",
                "Backtesting",
                "Multi-test leaderboard",
                "Strategies",
                "Reporting",
                "Risk & paper",
            ),
        )
        self.assertNotIn("Roadmap", pages)


if __name__ == "__main__":
    unittest.main()
