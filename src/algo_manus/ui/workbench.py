"""Functional local UI views backed by application services and fixture inputs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from algo_manus.application.leaderboard import LeaderboardSort

NAV_ITEMS = (
    ("Home", "Overview"),
    ("Data & instruments", "Data & instruments"),
    ("Backtesting", "Backtesting"),
    ("Multi-test leaderboard", "Multi-test leaderboard"),
    ("Strategies", "Strategies"),
    ("Reporting", "Reporting"),
    ("Risk & paper", "Risk & paper"),
    ("Roadmap", "Roadmap"),
)

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
    control_service = _local_risk_controls()
    instruments = service.instruments()
    by_id = {item.instrument_id: item for item in instruments}
    _state(st, tuple(by_id))

    with st.sidebar:
        st.markdown("## Algo Manus")
        st.caption("Local research workbench")
        st.success("FIXTURE MODE — LOCAL ONLY")
        st.caption(FIXTURE_MODE_LABEL)
        st.divider()
        page = _sidebar_navigation(st)
        st.divider()
        st.metric("Selected securities", len(st.session_state.selected_ids))
        st.metric("Saved local experiments", len(st.session_state.history))
        st.caption("Real broker sync remains separately gated.")

    if page == "Overview":
        _overview(st)
    elif page == "Data & instruments":
        _data_and_instruments(st, instruments, by_id, pd)
    elif page == "Backtesting":
        _research_lab(st, service, instruments, by_id, pd)
    elif page == "Multi-test leaderboard":
        _leaderboard(st, service, pd)
    elif page == "Strategies":
        _strategies(st, pd)
    elif page == "Reporting":
        _reporting(st, pd)
    elif page == "Risk & paper":
        _paper(st, by_id, pd, control_service)
    else:
        _roadmap(st, instruments, pd)


def _state(st, instrument_ids: tuple[str, ...]) -> None:
    st.session_state.setdefault("selected_ids", instrument_ids[:3])
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("active_batch", None)
    st.session_state.setdefault("paper_events", [])
    st.session_state.setdefault("workspace", "Overview")


def _local_risk_controls():
    """Return the local-only persistent control service used by the workbench."""

    from algo_manus.application.risk_controls import LocalRiskControlService
    from algo_manus.infrastructure.risk import SqliteRiskControlRepository

    data_root = Path(os.environ.get("ALGO_MANUS_DATA_DIR", str(Path.home() / ".algo-manus")))
    return LocalRiskControlService(SqliteRiskControlRepository(data_root / "risk_controls.sqlite3"))


def _sidebar_navigation(st) -> str:
    st.markdown("#### Workspace")
    for label, page in NAV_ITEMS:
        active = st.session_state.workspace == page
        if st.button(label, key=f"nav_{page}", type="primary" if active else "secondary"):
            st.session_state.workspace = page
            st.rerun()
    return st.session_state.workspace


def _style(st) -> None:
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
    metrics[3].metric("Paper safety", "Control console")
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Work flow")
        st.markdown("1. Search and select a local sample universe  \n2. Tune a versioned SMA revision  \n3. Run single or multi-security backtests  \n4. Inspect KPI rows, equity, trades and reports  \n5. Exercise a risk-gated paper event lifecycle")
    with right:
        st.subheader("Active experiment")
        if batch is None:
            st.info("No experiment yet. Open **Research lab** to run the local sample workflow.")
        else:
            st.success(batch.batch_id)
            st.caption(f"Strategy: {batch.strategy_id}")
            st.caption(f"Revision: {batch.parameter_revision_id}")
            st.caption(f"Snapshot: {batch.universe_snapshot_id}")


def _data_and_instruments(st, instruments, by_id, pd) -> None:
    _header(st, "Data & instruments", "Search the current local universe as you would the future broker-synced instrument master. Manual ticker entry is intentionally not used.")
    table = pd.DataFrame([
        {"Symbol": item.symbol, "Company": item.display_name, "Segment": item.segment, "Instrument identity": item.instrument_id, "Status": "Fixture active"}
        for item in instruments
    ])
    query, segment = st.columns([2.2, 1])
    term = query.text_input("Search symbol or company", placeholder="ALPHA, BRAVO, INDUSTRIES")
    selected_segment = segment.selectbox("Segment", ["All", "NSE Equity fixture"])
    filtered = table.copy()
    if term:
        mask = filtered["Symbol"].str.contains(term, case=False, na=False) | filtered["Company"].str.contains(term, case=False, na=False)
        filtered = filtered[mask]
    if selected_segment != "All":
        filtered = filtered[filtered["Segment"] == selected_segment]
    metrics = st.columns(4)
    metrics[0].metric("Instruments", len(table))
    metrics[1].metric("Matched", len(filtered))
    metrics[2].metric("Selected", len(st.session_state.selected_ids))
    metrics[3].metric("Source", "Fixture snapshot")
    st.dataframe(filtered, hide_index=True, width="stretch", height=260)
    chosen = st.multiselect(
        "Add instruments to the backtest universe",
        options=[item.instrument_id for item in instruments],
        default=st.session_state.selected_ids,
        format_func=lambda instrument_id: f"{by_id[instrument_id].symbol} — {by_id[instrument_id].display_name}",
    )
    st.session_state.selected_ids = tuple(chosen)
    st.caption("Future real-data mode will populate this table from a validated, versioned broker snapshot and flag unavailable or renamed instruments.")


def _research_lab(st, service, instruments, by_id, pd) -> None:
    _header(st, "Backtesting engine", "Run a reproducible single or multi-security local experiment with the same practical control layout used in a research terminal.")
    controls, output = st.columns([0.85, 1.55])
    with controls:
        st.subheader("Backtest controls")
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
        st.caption("The same SMA revision, costs and data interval are applied to every selected security.")
    with output:
        st.subheader("Backtest result")
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
        st.dataframe(trades, width="stretch", hide_index=True)
        st.caption(f"Result spec: {result.spec.spec_id} · Dataset: {result.spec.dataset_id}")


def _leaderboard(st, service, pd) -> None:
    _header(st, "Multi-security test leaderboard", "Run one strategy revision across a selected universe, then compare return and risk context in one detailed research table.")
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
    st.dataframe(frame, width="stretch", hide_index=True, height=330)
    if len(frame) > 1:
        st.bar_chart(frame.set_index("Instrument")[["Net P&L"]], height=260)
    st.download_button("Download fixture leaderboard CSV", frame.to_csv(index=False), "fixture_leaderboard.csv", "text/csv")
    with st.expander("Experiment history"):
        history = pd.DataFrame([
            {"Batch": item.batch_id, "Strategy": item.strategy_id, "Revision": item.parameter_revision_id,
             "Universe": len(item.results), "Created": item.created_at}
            for item in st.session_state.history
        ])
        st.dataframe(history.iloc[::-1], width="stretch", hide_index=True)


def _strategies(st, pd) -> None:
    _header(st, "Strategy manager", "Keep strategy definitions, parameter revisions and evaluation state visible. Only the SMA crossover implementation is currently available in fixture mode.")
    catalog = pd.DataFrame([
        {"Strategy": "SMA crossover", "Family": "Trend", "Revision model": "Immutable parameter revision", "Status": "Available in fixture mode", "Current controls": "Fast/slow windows"},
        {"Strategy": "EMA crossover", "Family": "Trend", "Revision model": "Planned", "Status": "Not implemented", "Current controls": "—"},
        {"Strategy": "RSI mean reversion", "Family": "Mean reversion", "Revision model": "Planned", "Status": "Not implemented", "Current controls": "—"},
        {"Strategy": "MACD signal", "Family": "Momentum", "Revision model": "Planned", "Status": "Not implemented", "Current controls": "—"},
    ])
    st.dataframe(catalog, hide_index=True, width="stretch")
    left, right = st.columns(2)
    with left:
        st.subheader("SMA parameter editor")
        st.number_input("Fast window preview", min_value=2, value=3, step=1, disabled=True)
        st.number_input("Slow window preview", min_value=4, value=6, step=1, disabled=True)
        st.info("Save a real revision by using the Backtesting page. This prevents dashboard-only edits from bypassing the application service.")
    with right:
        st.subheader("Evaluation status")
        st.metric("Active research implementation", "1")
        st.metric("Available historical experiment", len(st.session_state.history))
        st.caption("No performance scores are invented here. KPI values appear only after an actual local experiment run.")


def _reporting(st, pd) -> None:
    _header(st, "Reporting & analytics", "Read the active experiment’s aggregate evidence rather than generating random performance figures.")
    batch = st.session_state.active_batch
    if batch is None:
        st.info("Run a multi-security experiment first. Reporting is derived from stored local results only.")
        return
    rows = []
    trades = []
    for item in batch.results:
        result = item.backtest
        rows.append({"Instrument": item.instrument_id.split(":")[-1], "Net P&L": result.metrics.net_pnl, "Return %": result.metrics.total_return_pct, "Max DD %": result.metrics.max_drawdown_pct, "Trades": result.metrics.trade_count})
        trades.extend({"Instrument": item.instrument_id.split(":")[-1], "Entry": trade.entry_time, "Exit": trade.exit_time, "Net P&L": trade.net_pnl, "Cost": trade.cost} for trade in result.trades)
    frame = pd.DataFrame(rows)
    summary = st.columns(4)
    summary[0].metric("Aggregate net P&L", f"₹{frame['Net P&L'].sum():,.2f}")
    summary[1].metric("Securities tested", len(frame))
    summary[2].metric("Completed trades", int(frame["Trades"].sum()))
    summary[3].metric("Worst drawdown", f"{frame['Max DD %'].min():.2f}%")
    curves, log = st.tabs(["Equity comparison", "Trade log"])
    with curves:
        st.bar_chart(frame.set_index("Instrument")[["Net P&L"]], height=280)
        st.dataframe(frame, hide_index=True, width="stretch")
    with log:
        st.dataframe(pd.DataFrame(trades), hide_index=True, width="stretch", height=300)


def _paper(st, by_id, pd, control_service) -> None:
    from algo_manus.application.paper_execution import PaperExecutionService
    from algo_manus.domain.instruments import InstrumentStatus
    from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
    from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, OrderSide, PaperPortfolioSnapshot, RiskLimits
    from algo_manus.domain.risk_engine import CentralRiskPolicy

    _header(st, "Risk & paper operations", "Use the local risk policy, emergency kill switch and paper-event ledger with fixture marks only. No broker request or order is made.")
    batch = st.session_state.active_batch
    if batch is None:
        st.info("Run a fixture research experiment before using the paper simulator.")
        return
    fixture_policy = CentralRiskPolicy(
        policy_version="fixture-central-risk-v1",
        max_quantity_per_order=1_000,
        max_notional_per_order=100_000,
        max_open_positions=5,
    )
    snapshot = control_service.ensure_snapshot(
        fixture_policy,
        initial_kill_reason="initialized by local fixture workbench",
    )
    control_left, control_right, control_history = st.columns([0.9, 0.9, 1.45])
    control_left.metric("Active local policy", snapshot.policy.policy_version)
    control_right.metric("Durable kill state", "ACTIVE" if snapshot.kill_switch_active else "INACTIVE")
    with control_history:
        with st.expander("Persistent local control history", expanded=False):
            st.caption("Local SQLite control history only. It is not a broker, account or cloud control plane.")
            history = control_service.kill_switch_history()
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Time": item.occurred_at, "State": "ACTIVE" if item.active else "INACTIVE", "Reason": item.reason, "Change ID": item.change_id}
                        for item in history
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    change_left, change_right = st.columns([1.1, 0.9])
    with change_left:
        control_reason = st.text_input("Durable kill-switch change reason", value="local fixture operator action")
    with change_right:
        requested_kill_state = st.toggle("Set durable paper kill state active", value=snapshot.kill_switch_active)
        if st.button("Persist local kill-switch state"):
            control_service.set_kill_switch(active=requested_kill_state, reason=control_reason)
            st.rerun()
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

                def order_ids(self):
                    return frozenset(event.order_id for event in st.session_state.paper_events)

            intent = OrderIntent(
                order_id=f"fixture-paper-{len(st.session_state.paper_events) + 1}", instrument_id=instrument_id,
                side=side, quantity=quantity, reference_price=mark, strategy_revision_id=batch.parameter_revision_id,
            )
            validation = DatasetValidationOutcome(
                dataset_id=next(item.dataset_id for item in batch.results if item.instrument_id == instrument_id),
                status=DataValidationStatus.ACCEPTED,
                policy_version="fixture-paper-context-v1",
                validated_at=datetime.now(timezone.utc),
            )
            execution = PaperExecutionService(
                DeterministicRiskPolicy(),
                SessionLedger(),
                snapshot.policy,
            )
            submission = execution.submit(
                intent=intent, portfolio=PaperPortfolioSnapshot(cash=100_000, positions={}, realized_pnl=0, session_order_count=0),
                marks={instrument_id: mark}, limits=RiskLimits(max_gross_notional=250_000, max_notional_per_instrument=100_000, max_session_orders=5, max_daily_loss=10_000),
                kill_switch_active=snapshot.kill_switch_active,
                instrument_status=InstrumentStatus.ACTIVE,
                validation_outcome=validation,
                control_snapshot=snapshot,
            )
            if submission.decision.allowed:
                execution.fill(submission.order, fill_price=mark)
                st.success("Fixture order accepted and filled in the local event log.")
            else:
                st.error(f"Risk {submission.central_decision.decision_type.lower()} fixture order: {submission.decision.code}")
    with right:
        st.subheader("Local paper event ledger")
        if not st.session_state.paper_events:
            st.info("No fixture paper events yet.")
        else:
            latest_risk_event = next(
                (event for event in reversed(st.session_state.paper_events) if event.event_type.value == "RISK_DECISION"),
                None,
            )
            if latest_risk_event is not None:
                risk_evidence = json.loads(latest_risk_event.payload).get("payload", {})
                evidence = st.columns(3)
                evidence[0].metric("Latest central gate", risk_evidence.get("central_decision_type", "—"))
                evidence[1].metric("Central decision code", risk_evidence.get("central_decision_code", "—"))
                evidence[2].metric("Durable control", "ACTIVE" if risk_evidence.get("durable_kill_switch_active") else "INACTIVE")
                st.caption(
                    f"Policy {risk_evidence.get('central_policy_version', '—')} · "
                    f"Kill change {risk_evidence.get('kill_switch_change_id', '—')}"
                )
            frame = pd.DataFrame([
                {
                    "Time": event.occurred_at,
                    "Event": event.event_type,
                    "Order": event.order_id,
                    "Instrument": by_id[event.instrument_id].symbol,
                    "Central policy": json.loads(event.payload).get("payload", {}).get("central_policy_version"),
                    "Central decision": json.loads(event.payload).get("payload", {}).get("central_decision_type"),
                    "Central code": json.loads(event.payload).get("payload", {}).get("central_decision_code"),
                    "Durable kill change": json.loads(event.payload).get("payload", {}).get("kill_switch_change_id"),
                }
                for event in st.session_state.paper_events
            ])
            st.dataframe(frame.iloc[::-1], width="stretch", hide_index=True)


def _roadmap(st, instruments, pd) -> None:
    _header(st, "Readiness roadmap", "The workbench stays useful before broker approval because it uses explicit fixture mode, never silent fallback data.")
    st.dataframe(pd.DataFrame([
        {"Control": "Instrument master", "Current state": "Fixture sample only", "Real-data gate": "Approved broker master sync"},
        {"Control": "Research candles", "Current state": "Deterministic local bars", "Real-data gate": "Approved source, freshness and dataset validation"},
        {"Control": "Paper simulator", "Current state": "Local risk/event exercise", "Real-data gate": "Broker-authoritative marks and reconciled state"},
        {"Control": "Live execution", "Current state": "Unavailable", "Real-data gate": "Separate controlled pilot approval"},
    ]), width="stretch", hide_index=True)
    st.subheader("Current local fixture universe")
    st.dataframe(pd.DataFrame([
        {"Symbol": item.symbol, "Name": item.display_name, "Identity": item.instrument_id, "Segment": item.segment}
        for item in instruments
    ]), width="stretch", hide_index=True)
    st.warning("Fixture results are for workflow testing only. They must not be used to decide whether to buy, sell or deploy a strategy.")
