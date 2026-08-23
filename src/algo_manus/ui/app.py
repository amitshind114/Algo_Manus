"""Local Streamlit research shell.

This UI deliberately contains no provider SDK, strategy calculations, risk logic
or order-routing code. It makes operational state visible while application
services remain the single source of truth for all future actions.
"""

from __future__ import annotations


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Algo Manus — Local Research", layout="wide")
    st.title("Algo Manus — Local Research & Paper Operations")
    st.caption("Local-first research shell. Live execution is unavailable.")
    st.warning(
        "No broker master or research dataset is loaded in this build. "
        "A future, separately approved broker-data sync must populate the local cache first."
    )

    with st.sidebar:
        st.header("Local safety state")
        st.toggle("Paper safety switch", value=True, disabled=True)
        st.checkbox("Live execution", value=False, disabled=True)
        st.caption("The dashboard cannot enable live execution.")

    research, leaderboard, paper = st.tabs(
        ["Research workspace", "KPI leaderboard", "Paper operations"]
    )

    with research:
        st.subheader("Selected universe")
        st.info(
            "Instrument selection will appear only after a validated broker-master snapshot is available. "
            "The future workflow pins every test to that snapshot, strategy revision and data dataset."
        )
        st.selectbox("Validated instrument", options=["No broker snapshot available"], disabled=True)
        st.selectbox("Strategy revision", options=["SMA crossover — no saved revision"], disabled=True)
        st.button("Run reproducible backtest", disabled=True)
        st.caption("Backtests must run through the application service; UI buttons never calculate signals.")

    with leaderboard:
        st.subheader("Comparable multi-security experiment results")
        st.info(
            "No completed experiment batches are stored locally. Future rows will include return, drawdown, "
            "trade count, profit factor, win rate, data-quality note and reproducible result specification ID."
        )
        st.dataframe(
            {
                "Instrument": [],
                "Net P&L": [],
                "Return %": [],
                "Max drawdown %": [],
                "Trades": [],
                "Profit factor": [],
                "Data-quality note": [],
            },
            use_container_width=True,
            hide_index=True,
        )

    with paper:
        st.subheader("Paper-only order lifecycle")
        st.error("Paper submission is disabled until broker-authoritative marks and a validated universe are available.")
        st.caption(
            "Future paper actions require a deterministic risk decision and create an append-only local event ledger."
        )
        st.button("Submit paper order", disabled=True)


if __name__ == "__main__":
    main()
