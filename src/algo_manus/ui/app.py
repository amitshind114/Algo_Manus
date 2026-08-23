"""Streamlit entrypoint for the local Algo Manus research workbench."""

from __future__ import annotations


def main() -> None:
    import streamlit as st

    from algo_manus.ui.workbench import run_workbench

    st.set_page_config(page_title="Algo Manus", page_icon="AM", layout="wide", initial_sidebar_state="expanded")
    run_workbench(st)


if __name__ == "__main__":
    main()
