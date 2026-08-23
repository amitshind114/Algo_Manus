"""Functional local UI views backed by application services and fixture inputs."""

from __future__ import annotations

from algo_manus.application.leaderboard import LeaderboardSort

def leaderboard_sort_options() -> dict[str, LeaderboardSort]:
    """Keep the KPI sort mapping importable and testable outside Streamlit."""
    return {
        "Net P&L": LeaderboardSort.NET_PNL,
        "Return": LeaderboardSort.TOTAL_RETURN,
        "Drawdown": LeaderboardSort.MAX_DRAWDOWN,
        "Profit factor": LeaderboardSort.PROFIT_FACTOR,
        "Win rate": LeaderboardSort.WIN_RATE,
    }


def run_workbench(st) -> None:
    import pandas as pd

    from algo_manus.application.demo_workbench import FIXTURE_MODE_LABEL, FixtureWorkbenchService
    _style(st)
    service = FixtureWorkbenchService()
    instruments = service.instruments()
    by_id = {item.instrument_id: item for item in instruments}
    _state(st, tuple(by_id))

    with st.sidebar:
        st.markdown("## Algo Manus")
        st.caption("Local research workbench")
        st.success("FIXTURE MODE — LOCAL ONLY")
        st.caption(FIXTURE_MODE_LABEL)
        st.divider()
        page = st.selectbox(
            "Workspace",
            ["Overview", "Research lab", "KPI leaderboard", "Paper simulator", "Safety & data"],
        )
        st.divider()
        st.metric("Selected securities", len(st.session_state.selected_ids))
        st.metric("Saved local experiments", len(st.session_state.history))
        st.caption("Real broker sync remains separately gated.")

    if page == "Overview":
        _overview(st)
    elif page == "Research lab":
        _research_lab(st, service, instruments, by_id, pd)
    elif page == "KPI leaderboard":
        _leaderboard(st, service, pd)
    elif page == "Paper simulator":
        _paper(st, by_id, pd)
    else:
        _safety(st, instruments, pd)


def _state(st, instrument_ids: tuple[str, ...]) -> None:
    st.session_state.setdefault("selected_ids", instrument_ids[:3])
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("active_batch", None)
    st.session_state.setdefault("paper_events", [])
    st.session_state.setdefault("paper_kill", False)


def _style(st) -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f6f7f9; color: #172033; }
        [data-testid="stSidebar"] { background: #101828; min-width: 290px; }
        [data-testid="stSidebar"] * { color: #eef2f7; }
        [data-testid="stSidebar"] [data-baseweb="select"] * { color: #172033; }
        .kicker { color: #1d4ed8; font-size: .78rem; font-weight: 700; letter-spacing: .10em; }
        .title { font-size: 2.25rem; font-weight: 750; margin: .1rem 0 .25rem; }
        .fixture { background: #fff7dd; border: 1px solid #f5d689; color: #765700; border-radius: 10px; padding: 11px 14px; margin: 10px 0 20px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _header(st, title: str, subtitle: str) -> None:
    st.markdown('<div class="kicker">ALGO MANUS / LOCAL MODE</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="title">{title}</div>', unsafe_allow_html=True)
    st.caption(subtitle)
    st.markdown(
        '<div class="fixture"><b>Fixture mode:</b> all displayed results use deterministic local sample bars. '
        'They are not broker data, real market evidence or a trading recommendation.</div>',
        unsafe_allow_html=True,
    )


def _overview(st) -> None:
    _header(st, "Research command center", "A functional local workflow before broker data is separately approved.")
    batch = st.session_state.active_batch
    metrics = st.columns(4)
    metrics[0].metric("Universe", "Fixture NSE equity")
    metrics[1].metric("Selected", len(st.session_state.selected_ids))
    metrics[2].metric("Experiments", len(st.session_state.history))
    metrics[3].metric("Paper kill", "ON" if st.session_state.paper_kill else "OFF")
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Work flow")
        st.markdown("1. Select a local sample universe  \n2. Tune a versioned SMA revision  \n3. Run a multi-security backtest  \n4. Inspect KPI rows, equity and trades  \n5. Exercise a risk-gated paper event lifecycle")
    with right:
        st.subheader("Active experiment")
        if batch is None:
            st.info("No experiment yet. Open **Research lab** to run the local sample workflow.")
        else:
            st.success(batch.batch_id)
            st.caption(f"Strategy: {batch.strategy_id}")
            st.caption(f"Revision: {batch.parameter_revision_id}")
            st.caption(f"Snapshot: {batch.universe_snapshot_id}")


def _research_lab(st, service, instruments, by_id, pd) -> None:
    _header(st, "Research lab", "Select multiple securities, edit SMA parameters and run the actual application-level experiment service.")
    controls, output = st.columns([0.85, 1.55])
    with controls:
        st.subheader("Experiment setup")
        selected = st.multiselect(
            "Fixture NSE equity universe",
            options=[item.instrument_id for item in instruments],
            default=st.session_state.selected_ids,
            format_func=lambda instrument_id: f"{by_id[instrument_id].symbol} — {by_id[instrument_id].display_name}",
        )
        st.session_state.selected_ids = tuple(selected)
        fast = st.slider("Fast SMA window", 2, 6, 3)
        slow = st.slider("Slow SMA window", 4, 10, 6)
        capital = st.number_input("Starting cash per security", min_value=1_000.0, value=100_000.0, step=5_000.0)
        quantity = st.number_input("Simulated quantity", min_value=1, value=100, step=10)
        commission = st.number_input("Commission (bps)", min_value=0.0, value=10.0, step=1.0)
        slippage = st.number_input("Slippage (bps)", min_value=0.0, value=5.0, step=1.0)
        invalid = fast >= slow
        if invalid:
            st.error("Fast SMA must be lower than slow SMA.")
        run = st.button("Run fixture experiment", type="primary", disabled=invalid or not selected)
        st.caption("A run creates a parameter revision and snapshot-pinned experiment batch.")
    with output:
        st.subheader("Experiment output")
        if run:
            batch = service.run_experiment(
                selected_instrument_ids=tuple(selected), fast_window=fast, slow_window=slow,
                initial_cash=capital, quantity=quantity, commission_bps=commission, slippage_bps=slippage,
            )
            st.session_state.active_batch = batch
            st.session_state.history.append(batch)
            st.success(f"Created {batch.batch_id}")
        batch = st.session_state.active_batch
        if batch is None:
            st.info("Configure the local universe and run the experiment to populate this view.")
            return
        security = st.selectbox(
            "Inspect security result", [item.instrument_id for item in batch.results],
            format_func=lambda instrument_id: f"{by_id[instrument_id].symbol} — {by_id[instrument_id].display_name}",
        )
        result = next(item.backtest for item in batch.results if item.instrument_id == security)
        tiles = st.columns(4)
        tiles[0].metric("Net P&L", f"₹{result.metrics.net_pnl:,.2f}")
        tiles[1].metric("Return", f"{result.metrics.total_return_pct:.2f}%")
        tiles[2].metric("Max drawdown", f"{result.metrics.max_drawdown_pct:.2f}%")
        tiles[3].metric("Trades", result.metrics.trade_count)
        equity = pd.DataFrame(result.equity_curve, columns=["Timestamp", "Equity"])
        if not equity.empty:
            st.line_chart(equity.set_index("Timestamp"), height=230)
        trades = pd.DataFrame([
            {"Entry": trade.entry_time, "Exit": trade.exit_time, "Entry price": trade.entry_price,
             "Exit price": trade.exit_price, "Net P&L": trade.net_pnl, "Cost": trade.cost}
            for trade in result.trades
        ])
        st.dataframe(trades, use_container_width=True, hide_index=True)
        st.caption(f"Result spec: {result.spec.spec_id} · Dataset: {result.spec.dataset_id}")


def _leaderboard(st, service, pd) -> None:
    _header(st, "KPI leaderboard", "Compare the same parameter revision across the selected universe. Sorting does not label a result as the ‘best’ strategy.")
    batch = st.session_state.active_batch
    if batch is None:
        st.info("Run a local experiment in **Research lab** first.")
        return
    options = leaderboard_sort_options()
    rows = service.leaderboard(batch, options[st.selectbox("Sort by", list(options))])
    frame = pd.DataFrame([
        {"Instrument": row.instrument_id.split(":")[-1], "Net P&L": row.net_pnl, "Return %": row.total_return_pct,
         "Max DD %": row.max_drawdown_pct, "Trades": row.trade_count, "Win rate %": row.win_rate_pct,
         "Profit factor": row.profit_factor, "Data note": row.data_quality_note, "Result spec": row.result_spec_id}
        for row in rows
    ])
    tiles = st.columns(3)
    tiles[0].metric("Universe size", len(frame))
    tiles[1].metric("Parameter revision", batch.parameter_revision_id[-8:])
    tiles[2].metric("Dataset basis", "Fixture / 1d")
    st.dataframe(frame, use_container_width=True, hide_index=True)
    if len(frame) > 1:
        st.bar_chart(frame.set_index("Instrument")[["Net P&L"]], height=260)
    st.download_button("Download fixture leaderboard CSV", frame.to_csv(index=False), "fixture_leaderboard.csv", "text/csv")
    with st.expander("Experiment history"):
        history = pd.DataFrame([
            {"Batch": item.batch_id, "Strategy": item.strategy_id, "Revision": item.parameter_revision_id,
             "Universe": len(item.results), "Created": item.created_at}
            for item in st.session_state.history
        ])
        st.dataframe(history.iloc[::-1], use_container_width=True, hide_index=True)


def _paper(st, by_id, pd) -> None:
    from algo_manus.application.paper_execution import PaperExecutionService
    from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, OrderSide, PaperPortfolioSnapshot, RiskLimits

    _header(st, "Paper simulator", "Exercise the real deterministic risk policy and paper-event lifecycle using fixture marks only. No broker request or order is made.")
    batch = st.session_state.active_batch
    if batch is None:
        st.info("Run a fixture research experiment before using the paper simulator.")
        return
    st.toggle("Paper kill switch", key="paper_kill")
    left, right = st.columns([0.9, 1.45])
    with left:
        instrument_id = st.selectbox("Instrument", [item.instrument_id for item in batch.results], format_func=lambda item: by_id[item].symbol)
        side = st.selectbox("Side", [OrderSide.BUY, OrderSide.SELL])
        quantity = st.number_input("Fixture quantity", min_value=1, value=10, step=1)
        mark = st.number_input("Fixture mark", min_value=1.0, value=100.0, step=1.0)
        if st.button("Simulate risk-gated paper order", type="primary"):
            class SessionLedger:
                def append(self, event):
                    st.session_state.paper_events.append(event)

            intent = OrderIntent(
                order_id=f"fixture-paper-{len(st.session_state.paper_events) + 1}", instrument_id=instrument_id,
                side=side, quantity=quantity, reference_price=mark, strategy_revision_id=batch.parameter_revision_id,
            )
            execution = PaperExecutionService(DeterministicRiskPolicy(), SessionLedger())
            submission = execution.submit(
                intent=intent, portfolio=PaperPortfolioSnapshot(cash=100_000, positions={}, realized_pnl=0, session_order_count=0),
                marks={instrument_id: mark}, limits=RiskLimits(max_gross_notional=250_000, max_notional_per_instrument=100_000, max_session_orders=5, max_daily_loss=10_000),
                kill_switch_active=st.session_state.paper_kill,
            )
            if submission.decision.allowed:
                execution.fill(submission.order, fill_price=mark)
                st.success("Fixture order accepted and filled in the local event log.")
            else:
                st.error(f"Risk rejected fixture order: {submission.decision.code}")
    with right:
        st.subheader("Local paper event ledger")
        if not st.session_state.paper_events:
            st.info("No fixture paper events yet.")
        else:
            frame = pd.DataFrame([
                {"Time": event.occurred_at, "Event": event.event_type, "Order": event.order_id, "Instrument": by_id[event.instrument_id].symbol}
                for event in st.session_state.paper_events
            ])
            st.dataframe(frame.iloc[::-1], use_container_width=True, hide_index=True)


def _safety(st, instruments, pd) -> None:
    _header(st, "Safety & data boundaries", "The workbench stays useful before broker approval because it uses an explicit fixture mode, never silent fallback data.")
    st.dataframe(pd.DataFrame([
        {"Control": "Instrument master", "Current state": "Fixture sample only", "Real-data gate": "Approved broker master sync"},
        {"Control": "Research candles", "Current state": "Deterministic local bars", "Real-data gate": "Approved source, freshness and dataset validation"},
        {"Control": "Paper simulator", "Current state": "Local risk/event exercise", "Real-data gate": "Broker-authoritative marks and reconciled state"},
        {"Control": "Live execution", "Current state": "Unavailable", "Real-data gate": "Separate controlled pilot approval"},
    ]), use_container_width=True, hide_index=True)
    st.subheader("Fixture universe")
    st.dataframe(pd.DataFrame([
        {"Symbol": item.symbol, "Name": item.display_name, "Identity": item.instrument_id, "Segment": item.segment}
        for item in instruments
    ]), use_container_width=True, hide_index=True)
    st.warning("Fixture results are for workflow testing only. They must not be used to decide whether to buy, sell or deploy a strategy.")
