"""Local workbench runtime composition and session-state helpers.

These helpers construct local-only services for the Streamlit workbench.  They
never contact a broker, fetch market data during page render, or enable any
execution capability.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from algo_manus.ui.navigation import DEFAULT_PAGE, valid_pages


def local_data_root() -> Path:
    """Return the durable local research-data root."""

    return Path(os.environ.get("ALGO_MANUS_DATA_DIR", str(Path.home() / ".algo-manus")))


def initialize_workbench_state(
    st: Any,
    *,
    instrument_ids: tuple[str, ...],
    persisted_history,
) -> None:
    """Initialize and normalize workbench session state."""

    st.session_state.setdefault("selected_ids", instrument_ids[:3])
    st.session_state["history"] = list(persisted_history)
    persisted_by_id = {item.batch_id: item for item in persisted_history}
    active = st.session_state.get("active_batch")
    if active is None or active.batch_id not in persisted_by_id:
        st.session_state["active_batch"] = persisted_history[0] if persisted_history else None
    else:
        st.session_state["active_batch"] = persisted_by_id[active.batch_id]
    st.session_state.setdefault("workspace", DEFAULT_PAGE)
    if st.session_state.get("workspace") not in valid_pages():
        st.session_state["workspace"] = DEFAULT_PAGE


def local_public_instrument_source():
    """Return the manual public Angel master service."""

    from algo_manus.application.public_instrument_source import PublicInstrumentSourceService
    from algo_manus.infrastructure.instruments.angel_one import AngelScripMasterProvider
    from algo_manus.infrastructure.instruments.sqlite_repository import (
        SqliteInstrumentSnapshotRepository,
    )

    data_root = local_data_root()
    return PublicInstrumentSourceService(
        SqliteInstrumentSnapshotRepository(data_root / "instrument_master.sqlite3"),
        AngelScripMasterProvider(),
    )


def local_dhan_public_instrument_source():
    """Return the manual public Dhan master service."""

    from algo_manus.application.public_instrument_source import PublicInstrumentSourceService
    from algo_manus.infrastructure.instruments.dhan import DhanInstrumentMasterProvider
    from algo_manus.infrastructure.instruments.sqlite_repository import (
        SqliteInstrumentSnapshotRepository,
    )

    data_root = local_data_root()
    return PublicInstrumentSourceService(
        SqliteInstrumentSnapshotRepository(data_root / "instrument_master.sqlite3"),
        DhanInstrumentMasterProvider(),
    )


def local_authenticated_historical_source(st: Any):
    """Return session-scoped authenticated historical-source services."""

    from algo_manus.application.angel_session import LocalAngelSessionService
    from algo_manus.application.authenticated_historical_source import (
        AuthenticatedHistoricalCandleService,
    )
    from algo_manus.infrastructure.market_data.angel_one import AngelHistoricalCandleProvider
    from algo_manus.infrastructure.market_data.sqlite_repository import SqliteCandleDatasetRepository
    from algo_manus.infrastructure.sessions.angel_one import AngelSessionGateway

    if "angel_historical_source" not in st.session_state:
        data_root = local_data_root()
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


def local_retained_dataset_backtests():
    """Return the local retained-dataset backtesting service."""

    from algo_manus.application.retained_dataset_backtesting import RetainedDatasetBacktestService
    from algo_manus.infrastructure.experiments.sqlite_repository import SqliteExperimentBatchRepository
    from algo_manus.infrastructure.market_data.sqlite_repository import SqliteCandleDatasetRepository
    from algo_manus.infrastructure.research import SqliteResearchEvidenceRepository

    data_root = local_data_root()
    return RetainedDatasetBacktestService(
        SqliteCandleDatasetRepository(data_root / "market_data.sqlite3"),
        SqliteExperimentBatchRepository(data_root / "experiments.sqlite3"),
        SqliteResearchEvidenceRepository(data_root / "research_evidence.sqlite3"),
    )


def local_dhan_historical_panel(st: Any):
    """Return a Dhan panel only when a retained Dhan master snapshot exists."""

    from algo_manus.infrastructure.instruments.sqlite_repository import (
        SqliteInstrumentSnapshotRepository,
    )
    from algo_manus.infrastructure.market_data.dhan_historical import (
        DhanHistoricalCandleProvider,
    )
    from algo_manus.infrastructure.market_data.sqlite_repository import (
        SqliteCandleDatasetRepository,
    )
    from algo_manus.ui.dhan_historical import DhanHistoricalPanel

    data_root = local_data_root()
    snapshot = SqliteInstrumentSnapshotRepository(
        data_root / "instrument_master.sqlite3"
    ).latest("dhan")
    if snapshot is None:
        st.session_state.pop("dhan_historical_panel", None)
        return None
    cached = st.session_state.get("dhan_historical_panel")
    if cached is None or cached.instrument_snapshot_id != snapshot.snapshot_id:
        panel = DhanHistoricalPanel(
            provider=DhanHistoricalCandleProvider.from_environment(),
            repository=SqliteCandleDatasetRepository(data_root / "market_data.sqlite3"),
            instrument_snapshot=snapshot,
        )
        st.session_state["dhan_historical_panel"] = _DhanPanelHandle(
            panel=panel,
            instrument_snapshot_id=snapshot.snapshot_id,
        )
    return st.session_state["dhan_historical_panel"].panel


class _DhanPanelHandle:
    """Small session cache record that invalidates when the local master changes."""

    def __init__(self, *, panel: Any, instrument_snapshot_id: str) -> None:
        self.panel = panel
        self.instrument_snapshot_id = instrument_snapshot_id


def local_risk_controls():
    """Return the durable local-only risk-control service."""

    from algo_manus.application.risk_controls import LocalRiskControlService
    from algo_manus.infrastructure.risk import SqliteRiskControlRepository

    data_root = local_data_root()
    return LocalRiskControlService(SqliteRiskControlRepository(data_root / "risk_controls.sqlite3"))


def local_paper_ledger():
    """Return the durable local-only paper ledger."""

    from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger

    data_root = local_data_root()
    return SqlitePaperLedger(data_root / "paper_ledger.sqlite3")
