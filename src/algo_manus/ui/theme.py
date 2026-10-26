"""Shared Streamlit presentation helpers for the local research workbench."""

from __future__ import annotations

from typing import Any


def apply_workbench_style(st: Any) -> None:
    """Apply the stable workbench stylesheet."""

    st.markdown(
        """
        <style>
        .stApp { background: #f6f7f9; color: #172033; }
        [data-testid="stSidebar"] { background: #101828; min-width: 290px; }
        [data-testid="stSidebar"] * { color: #eef2f7; }
        [data-testid="stSidebar"] .stButton > button { width: 100%; justify-content: flex-start; border-radius: 7px; margin-bottom: 3px; color: #eef2f7 !important; }
        [data-testid="stSidebar"] .stButton > button[kind="secondary"] { background: #1d2939; border-color: #344054; color: #eef2f7 !important; }
        [data-testid="stSidebar"] .stButton > button[kind="primary"] { background: #1d4ed8; border-color: #1d4ed8; color: #ffffff !important; }
        .kicker { color: #1d4ed8; font-size: .78rem; font-weight: 700; letter-spacing: .10em; }
        .title { font-size: 2.25rem; font-weight: 750; margin: .1rem 0 .25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(st: Any, title: str, subtitle: str) -> None:
    """Render the standard workbench page header."""

    st.markdown('<div class="kicker">ALGO MANUS / RESEARCH WORKBENCH</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="title">{title}</div>', unsafe_allow_html=True)
    st.caption(subtitle)
