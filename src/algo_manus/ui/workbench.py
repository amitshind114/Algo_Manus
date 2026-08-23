"""Functional local UI views backed by application services and fixture inputs."""

from __future__ import annotations

from datetime import datetime, time, timezone
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
    service = FixtureWorkbenchService(_local_data_root())
    control_service = _local_risk_controls()
    paper_ledger = _local_paper_ledger()
    instruments = service.instruments()
    by_id = {item.instrument_id: item for item in instruments}
    _state(st, tuple(by_id), service.recent_experiments())

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
        _overview(st, service, pd)
    elif page == "Data & instruments":
        _data_and_instruments(st, instruments, by_id, pd)
    elif page == "Backtesting":
        _research_lab(st, service, instruments, by_id, pd)
    elif page == "Multi-test leaderboard":
        _leaderboard(st, service, pd)
    elif page == "Strategies":
        _strategies(st, pd)
    elif page == "Reporting":
        _reporting(st, service, pd)
    elif page == "Risk & paper":
        _paper(st, by_id, pd, service, control_service, paper_ledger)
    else:
        _roadmap(st, instruments, pd)


def _state(st, instrument_ids: tuple[str, ...], persisted_history) -> None:
    st.session_state.setdefault("selected_ids", instrument_ids[:3])
    st.session_state["history"] = list(persisted_history)
    persisted_by_id = {item.batch_id: item for item in persisted_history}
    active = st.session_state.get("active_batch")
    if active is None or active.batch_id not in persisted_by_id:
        st.session_state["active_batch"] = persisted_history[0] if persisted_history else None
    else:
        st.session_state["active_batch"] = persisted_by_id[active.batch_id]
    st.session_state.setdefault("workspace", "Overview")


def _local_risk_controls():
    """Return the local-only persistent control service used by the workbench."""

    from algo_manus.application.risk_controls import LocalRiskControlService
    from algo_manus.infrastructure.risk import SqliteRiskControlRepository

    data_root = _local_data_root()
    return LocalRiskControlService(SqliteRiskControlRepository(data_root / "risk_controls.sqlite3"))


def _local_paper_ledger():
    """Return the durable local-only paper ledger used by the fixture workbench."""

    from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger

    data_root = _local_data_root()
    return SqlitePaperLedger(data_root / "paper_ledger.sqlite3")


def _local_data_root() -> Path:
    return Path(os.environ.get("ALGO_MANUS_DATA_DIR", str(Path.home() / ".algo-manus")))


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


def _overview(st, service, pd) -> None:
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
    with st.expander("Local evidence lifecycle", expanded=False):
        lifecycle = service.evidence_lifecycle()
        all_history = service.evidence_health_history()
        st.caption("Read-only local fixture-store visibility. No cleanup, deletion, compaction, backup or cloud synchronization action is available here.")
        if all_history:
            scope_left, scope_right = st.columns(2)
            selected_scope_batch = scope_left.selectbox(
                "Lifecycle batch scope",
                ["All retained batches", *(item.batch_id for item in all_history)],
                key="lifecycle_batch_scope",
            )
            earliest = min(item.created_at for item in all_history).date()
            latest = max(item.created_at for item in all_history).date()
            selected_dates = scope_right.date_input(
                "Inclusive batch creation dates",
                value=(earliest, latest),
                min_value=earliest,
                max_value=latest,
                key="lifecycle_creation_scope",
            )
            if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
                created_from = datetime.combine(selected_dates[0], time.min, tzinfo=timezone.utc)
                created_until = datetime.combine(selected_dates[1], time.max, tzinfo=timezone.utc)
            else:
                created_from = datetime.combine(earliest, time.min, tzinfo=timezone.utc)
                created_until = datetime.combine(latest, time.max, tzinfo=timezone.utc)
            scope = service.evidence_health_scope(
                batch_id=None if selected_scope_batch == "All retained batches" else selected_scope_batch,
                created_from=created_from,
                created_until=created_until,
            )
            st.caption(f"Current local scope: {selected_scope_batch}; batch creation dates {selected_dates[0]} through {selected_dates[1]}. Scope changes only what is displayed.")
        else:
            scope = service.evidence_health_scope()
            st.info("No retained local experiment batches are available for lifecycle scope filtering.")
        health = scope.health
        first, second, third = st.columns(3)
        first.metric("Store", "Local SQLite" if lifecycle.is_persistent else "In-memory fixture")
        second.metric("Stored batches", lifecycle.batch_count)
        third.metric("Database size", f"{lifecycle.database_size_bytes:,} bytes")
        artifact_left, artifact_middle, artifact_right = st.columns(3)
        artifact_left.metric("Stored results", lifecycle.result_count)
        artifact_middle.metric("Artifact headers", lifecycle.artifact_count)
        artifact_right.metric("Completed local trades", lifecycle.completed_trade_count)
        health_left, health_middle, health_right = st.columns(3)
        health_left.metric("Integrity-complete results", health.complete_count)
        health_middle.metric("Results needing attention", health.non_complete_count)
        health_right.metric("Results checked", health.total_result_count)
        st.dataframe(
            pd.DataFrame(
                [
                    {"Local evidence field": "Equity points", "Value": lifecycle.equity_point_count},
                    {"Local evidence field": "Oldest batch", "Value": lifecycle.oldest_batch_created_at or "—"},
                    {"Local evidence field": "Newest batch", "Value": lifecycle.newest_batch_created_at or "—"},
                    {"Local evidence field": "Equity-point bound per result", "Value": lifecycle.max_equity_points_per_result or "In-memory only"},
                    {"Local evidence field": "Trade bound per result", "Value": lifecycle.max_trades_per_result or "In-memory only"},
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {"Artifact health status": "Complete", "Retained results": health.complete_count},
                    {"Artifact health status": "Unavailable", "Retained results": health.unavailable_count},
                    {"Artifact health status": "Incomplete", "Retained results": health.incomplete_count},
                    {"Artifact health status": "Result-spec mismatch", "Retained results": health.result_spec_mismatch_count},
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        details = scope.details
        detail_filter = st.selectbox(
            "Health detail filter",
            ["Non-complete", "All statuses", "Complete", "Unavailable", "Incomplete", "Result-spec mismatch"],
            key="lifecycle_health_detail_filter",
        )
        status_by_filter = {
            "Complete": "complete",
            "Unavailable": "unavailable",
            "Incomplete": "incomplete",
            "Result-spec mismatch": "result_spec_mismatch",
        }
        if detail_filter == "Non-complete":
            visible_details = [item for item in details if item.status.value != "complete"]
        elif detail_filter == "All statuses":
            visible_details = list(details)
        else:
            visible_details = [
                item for item in details if item.status.value == status_by_filter[detail_filter]
            ]
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Batch ID": item.batch_id,
                        "Instrument ID": item.instrument_id,
                        "Status": item.status.value,
                        "Result spec": item.result_spec_id,
                        "Artifact spec": item.artifact_result_spec_id or "—",
                        "Trades actual / expected": f"{item.actual_trade_count}/{item.expected_trade_count if item.expected_trade_count is not None else '—'}",
                        "Equity points actual / expected": f"{item.actual_equity_point_count}/{item.expected_equity_point_count if item.expected_equity_point_count is not None else '—'}",
                        "Batch created": item.created_at,
                    }
                    for item in visible_details
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        with st.expander("Chronological local health history", expanded=False):
            history = scope.history
            st.caption("Read-only retained batch coverage in oldest-to-newest creation order. It does not establish market-data coverage, strategy performance or evidence change causes.")
            if not history:
                st.info("No retained local experiment batches are available for health-history inspection.")
            else:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Batch created": item.created_at,
                                "Batch ID": item.batch_id,
                                "Results": item.total_result_count,
                                "Complete": item.complete_count,
                                "Unavailable": item.unavailable_count,
                                "Incomplete": item.incomplete_count,
                                "Spec mismatch": item.result_spec_mismatch_count,
                                "Needs attention": item.non_complete_count,
                            }
                            for item in history
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
        with st.expander("Compare two local batch health scopes", expanded=False):
            if len(all_history) < 2:
                st.info("At least two retained local batches are required for a side-by-side health comparison.")
            else:
                batch_ids = [item.batch_id for item in all_history]
                compare_left, compare_right = st.columns(2)
                left_batch_id = compare_left.selectbox(
                    "Left retained batch",
                    batch_ids,
                    key="lifecycle_compare_left",
                )
                right_batch_id = compare_right.selectbox(
                    "Right retained batch",
                    [item for item in batch_ids if item != left_batch_id],
                    key="lifecycle_compare_right",
                )
                comparison = service.evidence_health_comparison(
                    left_batch_id=left_batch_id,
                    right_batch_id=right_batch_id,
                )
                st.caption("Read-only current local health comparison. Delta means right retained batch minus left retained batch; it is not a performance, market or broker comparison.")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Local health count": "Results",
                                "Left": comparison.left.health.total_result_count,
                                "Right": comparison.right.health.total_result_count,
                                "Right − left": comparison.delta.total_result_count,
                            },
                            {
                                "Local health count": "Complete",
                                "Left": comparison.left.health.complete_count,
                                "Right": comparison.right.health.complete_count,
                                "Right − left": comparison.delta.complete_count,
                            },
                            {
                                "Local health count": "Unavailable",
                                "Left": comparison.left.health.unavailable_count,
                                "Right": comparison.right.health.unavailable_count,
                                "Right − left": comparison.delta.unavailable_count,
                            },
                            {
                                "Local health count": "Incomplete",
                                "Left": comparison.left.health.incomplete_count,
                                "Right": comparison.right.health.incomplete_count,
                                "Right − left": comparison.delta.incomplete_count,
                            },
                            {
                                "Local health count": "Result-spec mismatch",
                                "Left": comparison.left.health.result_spec_mismatch_count,
                                "Right": comparison.right.health.result_spec_mismatch_count,
                                "Right − left": comparison.delta.result_spec_mismatch_count,
                            },
                            {
                                "Local health count": "Needs attention",
                                "Left": comparison.left.health.non_complete_count,
                                "Right": comparison.right.health.non_complete_count,
                                "Right − left": comparison.delta.non_complete_count,
                            },
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
        st.caption("Counts describe locally retained fixture evidence only. They do not assess data quality, strategy performance, broker state or backup readiness, and they do not repair any result.")


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
            st.session_state.history = list(service.recent_experiments())
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
        integrity = service.experiment_artifact_integrity(
            batch_id=batch.batch_id, instrument_id=security
        )
        if not integrity.is_complete:
            st.warning(_artifact_status_message(integrity.status.value))
            artifacts = None
        else:
            try:
                artifacts = service.experiment_artifacts(batch_id=batch.batch_id, instrument_id=security)
            except (LookupError, ValueError):
                st.warning("Detailed local artifacts changed while being read and are unavailable for this saved result. KPI summaries remain persisted; no fixture result was recalculated.")
                artifacts = None
        if artifacts is not None:
            equity = pd.DataFrame(artifacts.equity_curve, columns=["Timestamp", "Equity"])
            if not equity.empty:
                st.line_chart(equity.set_index("Timestamp"), height=230)
            trades = pd.DataFrame([
                {"Entry": trade.entry_time, "Exit": trade.exit_time, "Entry price": trade.entry_price,
                 "Exit price": trade.exit_price, "Net P&L": trade.net_pnl, "Cost": trade.cost}
                for trade in artifacts.trades
            ])
            st.dataframe(trades, width="stretch", hide_index=True)
            st.caption(f"Persisted local artifact: {artifacts.result_spec_id}")
        st.caption(f"Result spec: {result.spec.spec_id} · Dataset: {result.spec.dataset_id}")


def _leaderboard(st, service, pd) -> None:
    _header(st, "Multi-security test leaderboard", "Run one strategy revision across a selected universe, then compare return and risk context in one detailed research table.")
    batch = _select_persisted_batch(st, key="leaderboard_batch")
    if batch is None:
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
             "Universe": len(item.results), "Created": item.created_at, "Research manifest": item.research_manifest_id}
            for item in st.session_state.history
        ])
        st.dataframe(history, width="stretch", hide_index=True)
        integrity_rows = _artifact_integrity_rows(service, st.session_state.history)
        st.caption("Detailed-artifact integrity is local SQLite evidence only. It does not re-run a fixture backtest or validate broker data.")
        filter_options = ["All", "complete", "unavailable", "incomplete", "result_spec_mismatch"]
        selected_status = st.selectbox("Artifact completeness filter", filter_options, key="history_artifact_status")
        if selected_status != "All":
            integrity_rows = [row for row in integrity_rows if row["Status"] == selected_status]
        st.dataframe(pd.DataFrame(integrity_rows), width="stretch", hide_index=True)


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


def _reporting(st, service, pd) -> None:
    _header(st, "Reporting & analytics", "Read the active experiment’s aggregate evidence rather than generating random performance figures.")
    batch = _select_persisted_batch(st, key="reporting_batch")
    if batch is None:
        return
    rows = []
    trades = []
    unavailable_details = []
    for item in batch.results:
        result = item.backtest
        rows.append({"Instrument": item.instrument_id.split(":")[-1], "Net P&L": result.metrics.net_pnl, "Return %": result.metrics.total_return_pct, "Max DD %": result.metrics.max_drawdown_pct, "Trades": result.metrics.trade_count})
        integrity = service.experiment_artifact_integrity(
            batch_id=batch.batch_id, instrument_id=item.instrument_id
        )
        if not integrity.is_complete:
            unavailable_details.append(
                f"{item.instrument_id.split(':')[-1]} ({integrity.status.value})"
            )
            continue
        try:
            artifacts = service.experiment_artifacts(
                batch_id=batch.batch_id, instrument_id=item.instrument_id
            )
        except (LookupError, ValueError):
            unavailable_details.append(f"{item.instrument_id.split(':')[-1]} (changed while read)")
            continue
        trades.extend({"Instrument": item.instrument_id.split(":")[-1], "Entry": trade.entry_time, "Exit": trade.exit_time, "Net P&L": trade.net_pnl, "Cost": trade.cost} for trade in artifacts.trades)
    frame = pd.DataFrame(rows)
    summary = st.columns(4)
    summary[0].metric("Aggregate net P&L", f"₹{frame['Net P&L'].sum():,.2f}")
    summary[1].metric("Securities tested", len(frame))
    summary[2].metric("Completed trades", int(frame["Trades"].sum()))
    summary[3].metric("Worst drawdown", f"{frame['Max DD %'].max():.2f}%")
    _local_evidence_export(st, service, batch, pd)
    curves, log = st.tabs(["Equity comparison", "Trade log"])
    with curves:
        st.bar_chart(frame.set_index("Instrument")[["Net P&L"]], height=280)
        st.dataframe(frame, hide_index=True, width="stretch")
    with log:
        if unavailable_details:
            st.warning("Detailed local trade artifacts are not complete for " + ", ".join(unavailable_details) + ". KPI summaries are still stored; no fixture result was recalculated.")
        st.dataframe(pd.DataFrame(trades), hide_index=True, width="stretch", height=300)


def _select_persisted_batch(st, *, key: str):
    history = st.session_state.history
    if not history:
        st.info("Run a persisted fixture experiment first.")
        return None
    active = st.session_state.active_batch
    selected_id = st.selectbox(
        "Persisted local experiment",
        options=[item.batch_id for item in history],
        index=next(
            (index for index, item in enumerate(history) if active is not None and item.batch_id == active.batch_id),
            0,
        ),
        key=key,
    )
    batch = next(item for item in history if item.batch_id == selected_id)
    st.session_state.active_batch = batch
    st.caption(f"Research manifest: {batch.research_manifest_id or 'missing — paper promotion blocked'}")
    return batch


def _artifact_integrity_rows(service, batches) -> list[dict[str, object]]:
    rows = []
    for batch in batches:
        for result in batch.results:
            integrity = service.experiment_artifact_integrity(
                batch_id=batch.batch_id, instrument_id=result.instrument_id
            )
            rows.append(
                {
                    "Batch": batch.batch_id,
                    "Instrument": result.instrument_id.split(":")[-1],
                    "Status": integrity.status.value,
                    "Trades": f"{integrity.actual_trade_count}/{integrity.expected_trade_count if integrity.expected_trade_count is not None else '—'}",
                    "Equity points": f"{integrity.actual_equity_point_count}/{integrity.expected_equity_point_count if integrity.expected_equity_point_count is not None else '—'}",
                    "Result spec match": integrity.result_spec_id == integrity.artifact_result_spec_id,
                }
            )
    return rows


def _artifact_status_message(status: str) -> str:
    messages = {
        "unavailable": "Detailed local equity and trade artifacts are unavailable for this saved batch. KPI summaries remain persisted; no fixture result was recalculated.",
        "incomplete": "Detailed local artifacts are incomplete for this saved batch. KPI summaries remain persisted; no fixture result was recalculated.",
        "result_spec_mismatch": "Detailed local artifacts do not match the saved result specification. KPI summaries remain persisted; no fixture result was recalculated.",
    }
    return messages.get(status, "Detailed local artifacts cannot be used for this saved batch. KPI summaries remain persisted; no fixture result was recalculated.")


def _local_evidence_export(st, service, batch, pd) -> None:
    with st.expander("Local evidence export", expanded=False):
        export = service.evidence_export(batch_id=batch.batch_id)
        st.caption("Fixture-only local evidence export. It is not broker data, market evidence, a performance certificate or an execution record.")
        status_frame = pd.DataFrame(
            [
                {
                    "Instrument": item.instrument_id.split(":")[-1],
                    "Artifact integrity": item.artifact_integrity.status.value,
                    "Trades": f"{item.artifact_integrity.actual_trade_count}/{item.artifact_integrity.expected_trade_count if item.artifact_integrity.expected_trade_count is not None else '—'}",
                    "Equity points": f"{item.artifact_integrity.actual_equity_point_count}/{item.artifact_integrity.expected_equity_point_count if item.artifact_integrity.expected_equity_point_count is not None else '—'}",
                }
                for item in export.results
            ]
        )
        st.dataframe(status_frame, hide_index=True, width="stretch")
        summary_payload = export.summary_payload()
        summary_verification = summary_payload["verification"]
        st.caption("Summary verification — canonical payload content only; this SHA-256 value is not a signature, broker confirmation or market-data certificate.")
        st.code(
            f"{summary_payload['schema']} v{summary_payload['schema_version']}\nsha256: {summary_verification['sha256']}",
            language="text",
        )
        st.download_button(
            "Download local evidence summary JSON",
            data=json.dumps(summary_payload, indent=2, sort_keys=True),
            file_name=f"{batch.batch_id}_fixture_evidence_summary.json",
            mime="application/json",
        )
        st.caption("Offline local verification (no upload or service call):")
        st.code(
            "python -m algo_manus.application.evidence_verification path/to/export.json",
            language="bash",
        )
        if export.detailed_export_allowed:
            detailed_payload = export.detailed_payload()
            detailed_verification = detailed_payload["verification"]
            st.caption("Detailed verification — compare this SHA-256 with the downloaded local detail JSON using the documented canonicalization method.")
            st.code(
                f"{detailed_payload['schema']} v{detailed_payload['schema_version']}\nsha256: {detailed_verification['sha256']}",
                language="text",
            )
            st.download_button(
                "Download integrity-complete local detail JSON",
                data=json.dumps(detailed_payload, indent=2, sort_keys=True),
                file_name=f"{batch.batch_id}_fixture_evidence_detail.json",
                mime="application/json",
            )
        else:
            st.info("Detailed local evidence export is refused because at least one stored artifact is not integrity-complete. The summary export remains available.")


def _paper(st, by_id, pd, service, control_service, ledger) -> None:
    from algo_manus.application.paper_audit import PaperOperationAuditTimelineReadService
    from algo_manus.application.paper_execution import PaperExecutionService
    from algo_manus.application.paper_projection import PaperOperationsReadService
    from algo_manus.application.paper_risk import PaperPortfolioRiskService
    from algo_manus.domain.instruments import InstrumentStatus
    from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, OrderSide, PaperPortfolioSnapshot, RiskLimits
    from algo_manus.domain.risk_engine import CentralRiskPolicy

    _header(st, "Risk & paper operations", "Use the local risk policy, emergency kill switch and paper-event ledger with fixture marks only. No broker request or order is made.")
    batch = st.session_state.active_batch
    if batch is None:
        st.info("Run a fixture research experiment before using the paper simulator.")
        return
    fixture_policy = CentralRiskPolicy(
        policy_version="fixture-central-risk-v2",
        max_quantity_per_order=1_000,
        max_notional_per_order=100_000,
        max_open_positions=5,
        max_gross_notional=250_000,
        max_notional_per_instrument=100_000,
        max_realized_loss=10_000,
        max_concentration_pct=100,
    )
    snapshot = control_service.ensure_snapshot(
        fixture_policy,
        initial_kill_reason="initialized by local fixture workbench",
    )
    paper_operations = PaperOperationsReadService(ledger)
    paper_audit = PaperOperationAuditTimelineReadService(ledger)
    fixture_starting_cash = 100_000.0
    projection = paper_operations.portfolio(starting_cash=fixture_starting_cash)
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
        promotion = service.paper_promotion(batch_id=batch.batch_id, instrument_id=instrument_id)
        if promotion is None:
            st.error("Paper promotion blocked: the selected experiment/instrument has no persisted accepted research evidence.")
        else:
            st.caption(f"Research manifest {promotion[0].manifest_id} · validation {promotion[0].validation_policy_version}")
        submit = st.button("Simulate risk-gated paper order", type="primary", disabled=promotion is None)
    fixture_marks = {position.instrument_id: position.average_entry_price for position in projection.positions}
    fixture_marks[instrument_id] = mark
    portfolio_risk = PaperPortfolioRiskService().snapshot(projection, marks=fixture_marks)
    if submit:
        with left:
            intent = OrderIntent(
                order_id=f"fixture-paper-{len(paper_operations.events()) + 1}", instrument_id=instrument_id,
                side=side, quantity=quantity, reference_price=mark, strategy_revision_id=batch.parameter_revision_id,
            )
            assert promotion is not None
            promotion_evidence, validation = promotion
            execution = PaperExecutionService(
                DeterministicRiskPolicy(),
                ledger,
                snapshot.policy,
                require_promotion_evidence=True,
            )
            submission = execution.submit(
                intent=intent,
                portfolio=PaperPortfolioSnapshot(
                    cash=projection.cash,
                    positions={position.instrument_id: position.quantity for position in projection.positions},
                    realized_pnl=projection.realized_pnl,
                    session_order_count=projection.session_order_count,
                ),
                marks=fixture_marks,
                limits=RiskLimits(max_gross_notional=250_000, max_notional_per_instrument=100_000, max_session_orders=5, max_daily_loss=10_000),
                kill_switch_active=snapshot.kill_switch_active,
                instrument_status=InstrumentStatus.ACTIVE,
                validation_outcome=validation,
                portfolio_risk=portfolio_risk,
                promotion_evidence=promotion_evidence,
                control_snapshot=snapshot,
            )
            if submission.decision.allowed:
                execution.fill(submission.order, fill_price=mark)
                st.success("Fixture order accepted and filled in the durable local event ledger.")
                st.rerun()
            else:
                st.error(f"Risk {submission.central_decision.decision_type.lower()} fixture order: {submission.decision.code}")
    with right:
        st.subheader("Durable local paper operations")
        projection_tiles = st.columns(4)
        projection_tiles[0].metric("Fixture starting cash", f"₹{fixture_starting_cash:,.0f}")
        projection_tiles[1].metric("Projected cash", f"₹{projection.cash:,.2f}")
        projection_tiles[2].metric("Realized P&L", f"₹{projection.realized_pnl:,.2f}")
        projection_tiles[3].metric("Open local positions", len(projection.positions))
        risk_tiles = st.columns(4)
        gross_limit = snapshot.policy.max_gross_notional or 0
        instrument_limit = snapshot.policy.max_notional_per_instrument or 0
        loss_limit = snapshot.policy.max_realized_loss or 0
        max_instrument_notional = max((notional for _, notional in portfolio_risk.instrument_notionals), default=0.0)
        risk_tiles[0].metric("Fixture gross exposure", f"₹{portfolio_risk.gross_notional:,.2f}", f"cap ₹{gross_limit:,.0f}")
        risk_tiles[1].metric("Largest fixture exposure", f"₹{max_instrument_notional:,.2f}", f"cap ₹{instrument_limit:,.0f}")
        risk_tiles[2].metric("Realized loss used", f"₹{max(0.0, -portfolio_risk.realized_pnl):,.2f}", f"cap ₹{loss_limit:,.0f}")
        risk_tiles[3].metric("Max concentration", f"{snapshot.policy.max_concentration_pct:.0f}%")
        st.caption("Exposure uses explicit fixture marks: the currently selected mark and average-entry marks for other local holdings. It is not broker valuation or reconciliation.")
        events = paper_operations.events()
        if not events:
            st.info("No durable fixture paper events yet.")
        else:
            latest_risk_event = next(
                (event for event in reversed(events) if event.event_type.value == "RISK_DECISION"),
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
                    "Research manifest": json.loads(event.payload).get("payload", {}).get("research_manifest_id"),
                }
                for event in events
            ])
            st.dataframe(frame.iloc[::-1], width="stretch", hide_index=True)
            with st.expander("Read-only local paper-operation audit timeline", expanded=False):
                audit_rows = paper_audit.rows()
                st.caption("Chronological retained local paper-event evidence only. It cannot submit, cancel, reconcile, amend, sync or route any order, and it is not broker confirmation.")
                if not audit_rows:
                    st.info("No retained local paper events are available for audit inspection.")
                else:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Time": item.occurred_at,
                                    "Event": item.event_type,
                                    "Lifecycle state": item.lifecycle_state,
                                    "Order": item.order_id,
                                    "Instrument": by_id.get(item.instrument_id, item.instrument_id).symbol if item.instrument_id in by_id else item.instrument_id,
                                    "Side": item.side or "—",
                                    "Quantity": item.quantity if item.quantity is not None else "—",
                                    "Reference price": item.reference_price if item.reference_price is not None else "—",
                                    "Fill price": item.fill_price if item.fill_price is not None else "—",
                                    "Decision": item.decision_code or "—",
                                    "Central gate": item.central_decision_type or "—",
                                    "Research batch": item.research_batch_id or "—",
                                    "Research manifest": item.research_manifest_id or "—",
                                    "Payload valid": item.payload_valid,
                                }
                                for item in audit_rows
                            ]
                        ),
                        hide_index=True,
                        width="stretch",
                    )
            positions = pd.DataFrame(
                [
                    {"Instrument": by_id.get(item.instrument_id, item.instrument_id).symbol if item.instrument_id in by_id else item.instrument_id,
                     "Quantity": item.quantity, "Average entry": item.average_entry_price}
                    for item in projection.positions
                ]
            )
            with st.expander("Replay projection details", expanded=False):
                st.caption("Derived from the durable local event ledger and the displayed fixture starting cash; it is not broker reconciliation.")
                st.dataframe(positions, hide_index=True, width="stretch")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"Order": item.order_id, "Instrument": item.instrument_id, "Side": item.side, "Quantity": item.quantity,
                             "State": item.status, "Fill price": item.fill_price}
                            for item in projection.orders
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
                if projection.unprojectable_event_ids:
                    st.warning(f"Unprojectable local event IDs: {', '.join(projection.unprojectable_event_ids)}")


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
