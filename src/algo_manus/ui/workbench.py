"""Functional local UI views backed by application services and fixture inputs."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

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
    public_instrument_source = _local_public_instrument_source()
    historical_candle_source, angel_session = _local_authenticated_historical_source(st)
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
        source_status = public_instrument_source.status()
        st.caption(
            "Angel public master: "
            + ("cached locally" if source_status.availability == "available" else "not downloaded")
        )
        historical_status = historical_candle_source.status()
        session_status = angel_session.status()
        st.caption(
            "Angel history: "
            + ("cached locally" if historical_status.availability == "available" else "local configuration required")
        )
        st.caption("Angel session: " + session_status.session_state.replace("_", " "))

    if page == "Overview":
        _overview(st, service, pd)
    elif page == "Data & instruments":
        _data_and_instruments(
            st,
            instruments,
            by_id,
            pd,
            public_instrument_source,
            historical_candle_source,
            angel_session,
        )
    elif page == "Backtesting":
        _research_lab(st, service, instruments, by_id, pd)
    elif page == "Multi-test leaderboard":
        _leaderboard(st, service, pd)
    elif page == "Strategies":
        _strategies(st, service, pd)
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


def _local_public_instrument_source():
    """Return the manual public Angel master service; no import or UI render downloads data."""

    from algo_manus.application.public_instrument_source import PublicInstrumentSourceService
    from algo_manus.infrastructure.instruments.angel_one import AngelScripMasterProvider
    from algo_manus.infrastructure.instruments.sqlite_repository import (
        SqliteInstrumentSnapshotRepository,
    )

    data_root = _local_data_root()
    return PublicInstrumentSourceService(
        SqliteInstrumentSnapshotRepository(data_root / "instrument_master.sqlite3"),
        AngelScripMasterProvider(),
    )


def _local_authenticated_historical_source(st):
    """Return session-scoped Option B/C services; UI rendering never requests broker data."""

    from algo_manus.application.angel_session import LocalAngelSessionService
    from algo_manus.application.authenticated_historical_source import (
        AuthenticatedHistoricalCandleService,
    )
    from algo_manus.infrastructure.market_data.angel_one import AngelHistoricalCandleProvider
    from algo_manus.infrastructure.market_data.sqlite_repository import SqliteCandleDatasetRepository
    from algo_manus.infrastructure.sessions.angel_one import AngelSessionGateway

    if "angel_historical_source" not in st.session_state:
        data_root = _local_data_root()
        provider = AngelHistoricalCandleProvider.from_environment()
        st.session_state["angel_historical_source"] = AuthenticatedHistoricalCandleService(
            SqliteCandleDatasetRepository(data_root / "market_data.sqlite3"), provider
        )
        st.session_state["angel_session_service"] = LocalAngelSessionService(
            AngelSessionGateway.from_environment(), provider
        )
    return (
        st.session_state["angel_historical_source"],
        st.session_state["angel_session_service"],
    )


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


def _data_and_instruments(
    st,
    instruments,
    by_id,
    pd,
    public_instrument_source,
    historical_candle_source,
    angel_session,
) -> None:
    _header(st, "Data & instruments", "Search the current local universe as you would the future broker-synced instrument master. Manual ticker entry is intentionally not used.")
    source_status = public_instrument_source.status()
    st.subheader("Angel One public instrument master")
    source_left, source_middle, source_right, source_action = st.columns([1.2, 1.1, 1.45, 1.35])
    source_left.metric("Public source", "Cached" if source_status.availability == "available" else "Not downloaded")
    source_middle.metric("Retained instruments", source_status.instrument_count)
    source_right.caption(
        "Snapshot: "
        + (source_status.snapshot_id or "No retained Angel One snapshot")
    )
    source_right.caption(
        "Last checked: "
        + (source_status.last_checked_at.isoformat() if source_status.last_checked_at else "Not yet checked")
    )
    with source_action:
        if st.button("Download public Angel master", type="secondary"):
            try:
                result = public_instrument_source.sync()
            except Exception as exc:
                st.error(f"Public Angel master was unavailable; no local snapshot changed: {exc}")
            else:
                st.success(
                    f"Manual source check completed: {result.reason}. "
                    f"Snapshot {result.snapshot.snapshot_id} is retained locally."
                )
                st.rerun()
    st.caption(
        "This action downloads only Angel One’s public ScripMaster JSON into an immutable local SQLite snapshot. "
        "It does not authenticate, access an account, fetch prices, submit paper orders or enable execution."
    )
    angel_preview = public_instrument_source.preview(limit=100)
    if angel_preview:
        with st.expander("Retained Angel One snapshot preview", expanded=False):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Symbol": item.trading_symbol,
                            "Name": item.display_name,
                            "Exchange": item.exchange,
                            "Type": item.instrument_type.value,
                            "Token": item.broker_token,
                            "Status": item.status.value,
                            "Instrument identity": item.instrument_id,
                        }
                        for item in angel_preview
                    ]
                ),
                hide_index=True,
                width="stretch",
                height=280,
            )
            st.caption(
                "Preview is read-only retained broker-master metadata. Historical candles and a broker-backed research universe remain separately gated."
            )
    else:
        st.info("No Angel One master is retained locally yet. Download the public master above to create the first immutable snapshot.")
    st.divider()
    _historical_candle_panel(st, pd, public_instrument_source, historical_candle_source, angel_session)
    st.divider()
    st.subheader("Current fixture research universe")
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
    st.caption("Fixture research remains separate until an approved historical-data source persists validated datasets. The retained Angel master above does not silently replace this universe.")


def _historical_candle_panel(
    st,
    pd,
    public_instrument_source,
    historical_candle_source,
    angel_session,
) -> None:
    """Render Option B local evidence controls without direct provider or database I/O."""

    from algo_manus.application.market_data import MarketDataRequest
    from algo_manus.domain.market_data import DataUseCase

    session_status = angel_session.status()
    status = historical_candle_source.status()
    st.subheader("Angel One authenticated historical candles")
    left, middle, right = st.columns([1.15, 1.1, 1.6])
    left.metric(
        "Historical source",
        "Cached" if status.availability == "available" else "Not downloaded",
    )
    middle.metric("Local configuration", "Ready" if status.credentials_configured else "Required")
    right.caption("Dataset: " + (status.dataset_id or "No retained candle dataset"))
    right.caption(
        "Last retrieved: " + (status.retrieved_at.isoformat() if status.retrieved_at else "Not yet retrieved")
    )
    st.caption(
        "This is a manual, research-only retrieval using a user-managed local app key and existing short-lived access token. "
        "It cannot sign in, refresh a token, access an account, retrieve live prices, open a WebSocket, submit paper orders or enable execution."
    )
    session_left, session_middle, session_right = st.columns(3)
    session_left.metric("Local session", session_status.session_state.replace("_", " ").title())
    session_middle.caption(
        "Acquired: " + (session_status.acquired_at.isoformat() if session_status.acquired_at else "Not in this browser session")
    )
    if session_status.session_state == "active_in_memory":
        if session_right.button("Refresh local session", key="refresh_angel_session"):
            try:
                angel_session.refresh()
            except Exception as exc:
                st.error(f"Session refresh was unavailable; the existing local session was retained: {exc}")
            else:
                st.success("Local in-memory session refreshed for read-only historical research.")
                st.rerun()
        if st.button("Forget local session", type="secondary", key="forget_angel_session"):
            angel_session.forget()
            st.info("The local in-memory session handoff was forgotten. No remote logout request was made.")
            st.rerun()
    elif session_status.credentials_configured:
        if session_right.button("Start local session", type="secondary", key="start_angel_session"):
            try:
                angel_session.start()
            except Exception as exc:
                st.error(f"Local session was unavailable; no token or dataset was retained: {exc}")
            else:
                st.success("Local in-memory session is ready for read-only historical research.")
                st.rerun()
    else:
        st.info(
            "Local session configuration is required before a candle request. Configure the documented local environment values yourself; "
            "do not paste credentials, client code, PIN, TOTP, refresh tokens or access tokens into this workbench or chat."
        )

    master = public_instrument_source.latest_snapshot()
    if master is None:
        st.info("A retained public Angel instrument-master snapshot is required before selecting a broker-backed historical-candle request.")
        return

    lookup = st.text_input(
        "Search retained Angel instrument for historical research",
        placeholder="RELIANCE, NIFTY, SENSEX",
        key="historical_instrument_lookup",
    ).strip()
    if not lookup:
        st.caption("Search the retained local Angel master to select a canonical instrument identity. Manual ticker entry is not used.")
        st.button(
            "Download research candles",
            type="secondary",
            disabled=True,
            key="download_historical_research_candles",
        )
        return
    normalized_lookup = lookup.upper()
    matches = [
        item
        for item in master.instruments
        if normalized_lookup in item.trading_symbol.upper() or normalized_lookup in item.display_name.upper()
    ][:100]
    if not matches:
        st.warning("No retained Angel instrument matches this local-master search.")
        return
    selected_id = st.selectbox(
        "Retained Angel instrument",
        [item.instrument_id for item in matches],
        format_func=lambda instrument_id: next(
            f"{item.trading_symbol} · {item.exchange} · token {item.broker_token}"
            for item in matches
            if item.instrument_id == instrument_id
        ),
        key="historical_instrument_id",
    )
    controls_left, controls_middle, controls_right = st.columns(3)
    interval = controls_left.selectbox(
        "Historical interval",
        ["1m", "3m", "5m", "10m", "15m", "30m", "1h", "1d"],
        index=7,
        key="historical_interval",
    )
    market_timezone = ZoneInfo("Asia/Kolkata")
    today = datetime.now(market_timezone).date()
    start_date = controls_middle.date_input(
        "Research start date",
        value=today - timedelta(days=7),
        max_value=today,
        key="historical_start_date",
    )
    end_date = controls_right.date_input(
        "Research end date",
        value=today,
        max_value=today,
        key="historical_end_date",
    )
    request_is_valid = start_date < end_date
    if not request_is_valid:
        st.error("Research end date must be later than research start date.")
    download = st.button(
        "Download research candles",
        type="secondary",
        disabled=not status.credentials_configured or not request_is_valid,
        key="download_historical_research_candles",
    )
    if download:
        request = MarketDataRequest(
            instrument_id=selected_id,
            interval=interval,
            start=datetime.combine(start_date, time(9, 15), tzinfo=market_timezone),
            end=datetime.combine(end_date, time(15, 30), tzinfo=market_timezone),
            use_case=DataUseCase.RESEARCH,
        )
        try:
            dataset = historical_candle_source.sync(request)
        except Exception as exc:
            st.error(f"Historical candle request was unavailable; no retained dataset changed: {exc}")
        else:
            st.success(f"Manual research retrieval retained immutable dataset {dataset.dataset_id}.")
            st.rerun()
    preview = historical_candle_source.preview(limit=100)
    if preview:
        with st.expander("Retained authenticated historical-candle preview", expanded=False):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Timestamp": candle.timestamp,
                            "Open": candle.open,
                            "High": candle.high,
                            "Low": candle.low,
                            "Close": candle.close,
                            "Volume": candle.volume,
                        }
                        for candle in preview
                    ]
                ),
                hide_index=True,
                width="stretch",
                height=280,
            )
            st.caption(
                "Preview is retained research evidence only. It does not replace fixture experiments, establish data quality or enable paper/execution workflows."
            )


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
        catalog = service.strategy_catalog()
        strategy_ids = [metadata.strategy_id for metadata in catalog]
        strategy_id = st.selectbox(
            "Local strategy",
            strategy_ids,
            format_func=lambda value: next(item.display_name for item in catalog if item.strategy_id == value),
        )
        metadata = next(item for item in catalog if item.strategy_id == strategy_id)
        parameters: dict[str, int | float] = {}
        for definition in metadata.parameter_schema.definitions:
            if definition.kind.value == "integer":
                parameters[definition.name] = st.number_input(
                    definition.description,
                    min_value=int(definition.minimum or 1),
                    max_value=int(definition.maximum or 500),
                    value=int(definition.default),
                    step=1,
                    key=f"strategy_{strategy_id}_{definition.name}",
                )
            else:
                parameters[definition.name] = st.number_input(
                    definition.description,
                    min_value=float(definition.minimum or 0.0),
                    max_value=float(definition.maximum or 100.0),
                    value=float(definition.default),
                    step=0.5,
                    key=f"strategy_{strategy_id}_{definition.name}",
                )
        invalid = False
        try:
            parameters = dict(service.validate_strategy_parameters(strategy_id, parameters))
        except ValueError as exc:
            invalid = True
            st.error(str(exc))
        capital = st.number_input("Starting cash per security", min_value=1_000.0, value=100_000.0, step=5_000.0)
        quantity = st.number_input("Simulated quantity", min_value=1, value=100, step=10)
        commission = st.number_input("Commission (bps)", min_value=0.0, value=10.0, step=1.0)
        slippage = st.number_input("Slippage (bps)", min_value=0.0, value=5.0, step=1.0)
        run = st.button("Run local experiment", type="primary", disabled=invalid or not selected)
        st.caption(f"{metadata.display_name} uses the same validated parameter revision, costs and data interval for every selected security.")
    with output:
        st.subheader("Backtest result")
        if run:
            batch = service.run_experiment(
                selected_instrument_ids=tuple(selected),
                strategy_id=strategy_id,
                parameters=parameters,
                initial_cash=capital,
                quantity=quantity,
                commission_bps=commission,
                slippage_bps=slippage,
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
        _render_backtest_outcome(st, result.outcome)
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
        {"Instrument": row.instrument_id.split(":")[-1], "Outcome": _backtest_outcome_label(row.outcome), "Net P&L": row.net_pnl, "Return %": row.total_return_pct,
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


def _strategies(st, service, pd) -> None:
    _header(st, "Strategy manager", "Inspect the registered high-value research families and create parameter revisions only through the Backtesting workflow.")
    metadata = service.strategy_catalog()
    catalog = pd.DataFrame([
        {
            "Strategy": item.display_name,
            "Strategy ID": item.strategy_id,
            "Version": item.version,
            "Status": "Available — local research",
            "Parameters": ", ".join(definition.name for definition in item.parameter_schema.definitions),
            "Risk boundary": item.risk_notes,
        }
        for item in metadata
    ])
    st.dataframe(catalog, hide_index=True, width="stretch")
    left, right = st.columns(2)
    with left:
        selected_id = st.selectbox(
            "Inspect registered strategy",
            [item.strategy_id for item in metadata],
            format_func=lambda value: next(item.display_name for item in metadata if item.strategy_id == value),
        )
        selected = next(item for item in metadata if item.strategy_id == selected_id)
        st.subheader(selected.display_name)
        st.caption(selected.description)
        for definition in selected.parameter_schema.definitions:
            st.caption(f"{definition.name}: default {definition.default}; {definition.description}")
        st.info("Create and persist a real parameter revision by using the Backtesting page. The strategy manager does not calculate or save dashboard-only results.")
    with right:
        st.subheader("Evaluation status")
        st.metric("Registered research strategies", len(metadata))
        st.metric("Available historical experiments", len(st.session_state.history))
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
        rows.append({"Instrument": item.instrument_id.split(":")[-1], "Outcome": _backtest_outcome_label(result.outcome), "Net P&L": result.metrics.net_pnl, "Return %": result.metrics.total_return_pct, "Max DD %": result.metrics.max_drawdown_pct, "Trades": result.metrics.trade_count})
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


def _backtest_outcome_label(outcome) -> str:
    if outcome is None:
        return "Legacy result — outcome details unavailable"
    return outcome.kind.value.replace("_", " ").title()


def _render_backtest_outcome(st, outcome) -> None:
    if outcome is None:
        st.info("This saved local result predates calculation-outcome details. KPI values are retained, but signal context is unavailable.")
        return
    if outcome.completed_trade_count:
        st.success(outcome.message)
    else:
        st.info(outcome.message)
    st.caption(
        "Calculation context — "
        f"{outcome.available_bar_count} bars available · {outcome.required_history} bars required · "
        f"{outcome.enter_signal_count} entry signal(s) · {outcome.exit_signal_count} exit signal(s) · "
        f"{outcome.completed_trade_count} completed trade(s)."
    )


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
                st.caption("Chronological retained local paper-event evidence only. It cannot submit, cancel, reconcile, amend, sync or route any order, and it is not broker confirmation.")
                all_audit_rows = paper_audit.rows()
                if not all_audit_rows:
                    st.info("No retained local paper events are available for audit inspection.")
                else:
                    retained_order_ids = sorted({item.order_id for item in all_audit_rows})
                    selected_audit_order_id = st.selectbox(
                        "Retained local order scope",
                        options=["All retained local orders", *retained_order_ids],
                        help="Changes only the displayed retained local audit rows; it has no paper-operation or broker effect.",
                    )
                    selected_preset = st.selectbox(
                        "Local audit scope preset",
                        options=[
                            "Manual integrity filter",
                            "All retained events preset",
                            "Valid interpretations preset",
                            "Integrity issues preset",
                        ],
                        help="Presets only set the local audit integrity dimension; retained order, event, instrument and UTC time filters remain independent and read-only.",
                    )
                    preset_identifier = {
                        "All retained events preset": "ALL",
                        "Valid interpretations preset": "VALID",
                        "Integrity issues preset": "ISSUES",
                    }.get(selected_preset)
                    if preset_identifier is None:
                        selected_integrity_scope = st.selectbox(
                            "Local audit integrity scope",
                            options=["All retained events", "Valid interpretation only", "Integrity issues only"],
                            help="Changes only the displayed local audit interpretation rows; it cannot repair, reconcile or affect any paper operation.",
                        )
                        integrity_filter = {
                            "All retained events": "ALL",
                            "Valid interpretation only": "VALID",
                            "Integrity issues only": "ISSUES",
                        }[selected_integrity_scope]
                    else:
                        preset = paper_audit.scope_preset(preset_identifier)
                        selected_integrity_scope = preset.label
                        integrity_filter = preset.integrity_filter
                        st.caption(
                            f"Preset `{preset.label}` sets only the local integrity scope; the remaining local filters stay unchanged."
                        )
                    selected_event_type_scope = st.selectbox(
                        "Retained local event type",
                        options=[
                            "All retained event types",
                            "Risk decisions",
                            "Submissions",
                            "Fills",
                            "Cancellations",
                            "Rejections",
                        ],
                        help="Changes only the displayed retained local audit events; it cannot alter lifecycle, paper-operation or broker state.",
                    )
                    event_type_filter = {
                        "All retained event types": "ALL",
                        "Risk decisions": "RISK_DECISION",
                        "Submissions": "ORDER_SUBMITTED",
                        "Fills": "ORDER_FILLED",
                        "Cancellations": "ORDER_CANCELLED",
                        "Rejections": "ORDER_REJECTED",
                    }[selected_event_type_scope]
                    selected_lifecycle_state_scope = st.selectbox(
                        "Interpreted local lifecycle state",
                        options=[
                            "All interpreted lifecycle states",
                            "Pending-risk state",
                            "Submitted state",
                            "Filled state",
                            "Cancelled state",
                            "Rejected state",
                            "Unprojectable lifecycle state",
                        ],
                        help="Changes only the displayed retained local audit rows by their already-interpreted lifecycle state; it cannot alter lifecycle, paper-operation or broker state.",
                    )
                    lifecycle_state_filter = {
                        "All interpreted lifecycle states": "ALL",
                        "Pending-risk state": "PENDING_RISK",
                        "Submitted state": "SUBMITTED",
                        "Filled state": "FILLED",
                        "Cancelled state": "CANCELLED",
                        "Rejected state": "REJECTED",
                        "Unprojectable lifecycle state": "UNPROJECTABLE",
                    }[selected_lifecycle_state_scope]
                    selected_side_scope = st.selectbox(
                        "Retained local payload side",
                        options=["All retained payload sides", "Buy payload side", "Sell payload side"],
                        help="Changes only the displayed retained local audit rows by their already-interpreted payload side; it cannot alter lifecycle, paper-operation or broker state.",
                    )
                    side_filter = {
                        "All retained payload sides": "ALL",
                        "Buy payload side": "BUY",
                        "Sell payload side": "SELL",
                    }[selected_side_scope]
                    retained_instrument_ids = sorted({item.instrument_id for item in all_audit_rows})
                    selected_instrument_id = st.selectbox(
                        "Retained local instrument scope",
                        options=["All retained local instruments", *retained_instrument_ids],
                        help="Changes only the displayed retained local audit rows; it cannot alter lifecycle, paper-operation or broker state.",
                    )
                    instrument_id_filter = (
                        None
                        if selected_instrument_id == "All retained local instruments"
                        else selected_instrument_id
                    )
                    retained_start = min(item.occurred_at for item in all_audit_rows)
                    retained_end = max(item.occurred_at for item in all_audit_rows)
                    time_window_enabled = st.checkbox(
                        "Limit retained local audit time window (UTC)",
                        value=False,
                        help="Changes only the displayed retained local audit rows and totals; it cannot alter the local ledger, paper operations or broker state.",
                    )
                    start_time: datetime | None = None
                    end_time: datetime | None = None
                    if time_window_enabled:
                        start_column, end_column = st.columns(2)
                        with start_column:
                            start_date = st.date_input(
                                "Audit start date (UTC)",
                                value=retained_start.date(),
                                min_value=retained_start.date(),
                                max_value=retained_end.date(),
                            )
                            start_clock = st.time_input(
                                "Audit start time (UTC)",
                                value=retained_start.time().replace(tzinfo=None),
                            )
                        with end_column:
                            end_date = st.date_input(
                                "Audit end date (UTC)",
                                value=retained_end.date(),
                                min_value=retained_start.date(),
                                max_value=retained_end.date(),
                            )
                            end_clock = st.time_input(
                                "Audit end time (UTC)",
                                value=retained_end.time().replace(tzinfo=None),
                            )
                        start_time = datetime.combine(start_date, start_clock, tzinfo=timezone.utc)
                        end_time = datetime.combine(end_date, end_clock, tzinfo=timezone.utc)
                    selected_order_id = (
                        None if selected_audit_order_id == "All retained local orders" else selected_audit_order_id
                    )
                    invalid_time_window = start_time is not None and end_time is not None and start_time > end_time
                    if invalid_time_window:
                        st.warning("Audit start time must not be after audit end time.")
                        audit_rows = ()
                        integrity = None
                        filter_summary = None
                    else:
                        audit_rows = paper_audit.rows(
                            order_id=selected_order_id,
                            integrity_filter=integrity_filter,
                            event_type_filter=event_type_filter,
                            lifecycle_state_filter=lifecycle_state_filter,
                            instrument_id_filter=instrument_id_filter,
                            side_filter=side_filter,
                            start_time=start_time,
                            end_time=end_time,
                        )
                        integrity = paper_audit.integrity(
                            order_id=selected_order_id,
                            integrity_filter=integrity_filter,
                            event_type_filter=event_type_filter,
                            lifecycle_state_filter=lifecycle_state_filter,
                            instrument_id_filter=instrument_id_filter,
                            side_filter=side_filter,
                            start_time=start_time,
                            end_time=end_time,
                        )
                        filter_summary = paper_audit.filter_summary(
                            order_id=selected_order_id,
                            integrity_filter=integrity_filter,
                            event_type_filter=event_type_filter,
                            lifecycle_state_filter=lifecycle_state_filter,
                            instrument_id_filter=instrument_id_filter,
                            side_filter=side_filter,
                            start_time=start_time,
                            end_time=end_time,
                        )
                    if filter_summary is not None:
                        st.markdown("#### Active read-only audit filters")
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {"Filter": "Retained order", "Active local scope": filter_summary.order_scope},
                                    {"Filter": "Integrity", "Active local scope": filter_summary.integrity_scope},
                                    {"Filter": "Event type", "Active local scope": filter_summary.event_type_scope},
                                    {
                                        "Filter": "Interpreted lifecycle state",
                                        "Active local scope": filter_summary.lifecycle_state_scope,
                                    },
                                    {"Filter": "Retained payload side", "Active local scope": filter_summary.side_scope},
                                    {"Filter": "Retained instrument", "Active local scope": filter_summary.instrument_scope},
                                    {
                                        "Filter": "UTC start (inclusive)",
                                        "Active local scope": filter_summary.start_time.isoformat()
                                        if filter_summary.start_time is not None
                                        else "ALL",
                                    },
                                    {
                                        "Filter": "UTC end (inclusive)",
                                        "Active local scope": filter_summary.end_time.isoformat()
                                        if filter_summary.end_time is not None
                                        else "ALL",
                                    },
                                ]
                            ),
                            hide_index=True,
                            width="stretch",
                        )
                        st.caption(
                            "This is a local read-only summary of displayed audit filters. It cannot repair, reconcile, export, synchronize or change paper operations."
                        )
                    if selected_audit_order_id != "All retained local orders":
                        st.caption(f"Showing retained local audit rows for order `{selected_audit_order_id}` only.")
                    if selected_integrity_scope != "All retained events":
                        st.caption(f"Showing `{selected_integrity_scope.lower()}` within the selected local audit scope.")
                    if selected_event_type_scope != "All retained event types":
                        st.caption(f"Showing `{selected_event_type_scope.lower()}` within the selected local audit scope.")
                    if selected_lifecycle_state_scope != "All interpreted lifecycle states":
                        st.caption(
                            f"Showing `{selected_lifecycle_state_scope.lower()}` within the selected local audit scope."
                        )
                    if selected_side_scope != "All retained payload sides":
                        st.caption(f"Showing `{selected_side_scope.lower()}` within the selected local audit scope.")
                    if selected_instrument_id != "All retained local instruments":
                        st.caption(f"Showing retained local audit rows for instrument `{selected_instrument_id}` only.")
                    if time_window_enabled and not invalid_time_window:
                        st.caption(
                            "Showing retained local audit rows inclusively from "
                            f"`{start_time.isoformat()}` to `{end_time.isoformat()}`."
                        )
                    if integrity is not None:
                        integrity_tiles = st.columns(4)
                        integrity_tiles[0].metric("Retained events", integrity.total_events)
                        integrity_tiles[1].metric("Valid interpretation", integrity.valid_events)
                        integrity_tiles[2].metric("Malformed payload", integrity.malformed_payload_events)
                        integrity_tiles[3].metric("Invalid lifecycle", integrity.invalid_lifecycle_events)
                    st.caption("Integrity is a read-only interpretation of retained local payload shape and lifecycle order. It does not repair, reconcile or confirm any broker or execution state.")
                    if not audit_rows:
                        if invalid_time_window:
                            st.info("Correct the local audit time window before inspecting retained audit rows.")
                        else:
                            st.info("No retained local audit rows match the selected audit filters.")
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
                                        "Audit integrity": item.integrity_status,
                                    }
                                    for item in audit_rows
                                ]
                            ),
                            hide_index=True,
                            width="stretch",
                        )
                        with st.expander("Read-only retained audit-row detail", expanded=False):
                            st.caption(
                                "Local retained payload and interpreted fields only. This view cannot amend, reconcile, export, synchronize or change any paper operation."
                            )
                            selected_audit_event_id = st.selectbox(
                                "Retained local audit event",
                                options=[item.event_id for item in audit_rows],
                                format_func=lambda event_id: next(
                                    f"{item.occurred_at.isoformat()} · {item.event_type} · {event_id}"
                                    for item in audit_rows
                                    if item.event_id == event_id
                                ),
                                help="Changes only the displayed retained local audit row detail.",
                            )
                            detail = paper_audit.row_detail(selected_audit_event_id)
                            detail_row = detail.row
                            st.dataframe(
                                pd.DataFrame(
                                    [
                                        {"Field": "Event ID", "Retained or interpreted value": detail_row.event_id},
                                        {"Field": "Recorded time", "Retained or interpreted value": detail_row.occurred_at.isoformat()},
                                        {"Field": "Event type", "Retained or interpreted value": detail_row.event_type},
                                        {"Field": "Derived lifecycle state", "Retained or interpreted value": detail_row.lifecycle_state},
                                        {"Field": "Audit integrity", "Retained or interpreted value": detail_row.integrity_status},
                                        {"Field": "Payload valid", "Retained or interpreted value": detail_row.payload_valid},
                                        {"Field": "Order", "Retained or interpreted value": detail_row.order_id},
                                        {"Field": "Instrument", "Retained or interpreted value": detail_row.instrument_id},
                                        {"Field": "Side", "Retained or interpreted value": detail_row.side or "—"},
                                        {"Field": "Quantity", "Retained or interpreted value": detail_row.quantity if detail_row.quantity is not None else "—"},
                                        {"Field": "Reference price", "Retained or interpreted value": detail_row.reference_price if detail_row.reference_price is not None else "—"},
                                        {"Field": "Fill price", "Retained or interpreted value": detail_row.fill_price if detail_row.fill_price is not None else "—"},
                                        {"Field": "Decision code", "Retained or interpreted value": detail_row.decision_code or "—"},
                                        {"Field": "Central gate", "Retained or interpreted value": detail_row.central_decision_type or "—"},
                                        {"Field": "Research batch", "Retained or interpreted value": detail_row.research_batch_id or "—"},
                                        {"Field": "Research manifest", "Retained or interpreted value": detail_row.research_manifest_id or "—"},
                                    ]
                                ),
                                hide_index=True,
                                width="stretch",
                            )
                            st.caption("Retained local payload")
                            st.code(
                                detail.retained_payload,
                                language="json" if detail_row.payload_valid else None,
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
