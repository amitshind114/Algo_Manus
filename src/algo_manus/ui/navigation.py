"""Stable sidebar navigation for the local research workbench."""

from __future__ import annotations

from typing import Any

NAV_ITEMS = (
    ("Home", "Overview"),
    ("Data & instruments", "Data & instruments"),
    ("Backtesting", "Backtesting"),
    ("Multi-test leaderboard", "Multi-test leaderboard"),
    ("Strategies", "Strategies"),
    ("Reporting", "Reporting"),
    ("Risk & paper", "Risk & paper"),
)

DEFAULT_PAGE = "Overview"


def valid_pages() -> frozenset[str]:
    """Return the set of valid workbench pages."""

    return frozenset(page for _, page in NAV_ITEMS)


def normalize_page(page: str | None) -> str:
    """Return a valid page, falling back to the default page."""

    if page in valid_pages():
        return page  # type: ignore[return-value]
    return DEFAULT_PAGE


def render_sidebar_navigation(st: Any) -> str:
    """Render sidebar navigation and return the active page."""

    st.markdown("#### Workspace")
    for label, page in NAV_ITEMS:
        active = st.session_state.workspace == page
        if st.button(label, key=f"nav_{page}", type="primary" if active else "secondary"):
            st.session_state.workspace = page
            st.rerun()
    return st.session_state.workspace
