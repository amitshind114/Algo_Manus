"""Isolated Streamlit panel for manual Dhan historical-candle retrieval.

This module is research-only.  It never renders a network request during page
load, never accesses account data, never exposes credentials, and contains no
order, position, WebSocket, scheduler, or cloud-execution capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from algo_manus.application.market_data import MarketDataRequest, MarketDataService
from algo_manus.domain.market_data import DataUseCase
from algo_manus.infrastructure.market_data.dhan_historical import DhanHistoricalCandleProvider
from algo_manus.infrastructure.market_data.sqlite_repository import SqliteCandleDatasetRepository

SUPPORTED_INTERVALS = ("1d", "1m", "5m", "15m", "25m", "60m")
MAX_INTRADAY_WINDOW = timedelta(days=90)


@dataclass(frozen=True, slots=True)
class DhanRetrievalForm:
    instrument_id: str
    interval: str
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if not self.instrument_id.strip():
            raise ValueError("A Dhan canonical instrument ID is required")
        if self.interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported Dhan historical interval: {self.interval}")
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Request bounds must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("Start must be earlier than end")
        if self.interval != "1d" and self.end - self.start > MAX_INTRADAY_WINDOW:
            raise ValueError("Dhan intraday requests are limited to 90 days")


class DhanHistoricalPanel:
    """Compose the Dhan historical-data retrieval workflow for Streamlit."""

    def __init__(
        self,
        *,
        provider: DhanHistoricalCandleProvider,
        repository: SqliteCandleDatasetRepository,
    ) -> None:
        self._provider = provider
        self._service = MarketDataService(repository)

    @property
    def configuration_status(self) -> str:
        if self._provider.credentials_configured:
            return "configured"
        return "configuration-required"

    @property
    def configuration_message(self) -> str:
        return self._provider.configuration_message

    def retrieve(self, form: DhanRetrievalForm, *, retrieved_at: datetime) -> dict[str, Any]:
        """Perform one explicit, bounded research-only retrieval."""

        dataset = self._service.ingest(
            self._provider,
            MarketDataRequest(
                instrument_id=form.instrument_id,
                interval=form.interval,
                start=form.start,
                end=form.end,
                use_case=DataUseCase.RESEARCH,
            ),
            retrieved_at=retrieved_at,
        )
        return {
            "dataset_id": dataset.dataset_id,
            "instrument_id": dataset.instrument_id,
            "interval": dataset.interval,
            "source_name": dataset.provenance.source_name,
            "source_kind": dataset.provenance.source_kind.value,
            "use_case": dataset.provenance.use_case.value,
            "adjustment_basis": dataset.provenance.adjustment_basis,
            "raw_content_sha256": dataset.provenance.raw_content_sha256,
            "candle_count": len(dataset.candles),
            "first_candle": dataset.candles[0].timestamp,
            "last_candle": dataset.candles[-1].timestamp,
        }


def render_dhan_historical_panel(st: Any, panel: DhanHistoricalPanel) -> None:
    """Render the manual Dhan historical-retrieval panel."""

    st.subheader("Dhan historical data")
    st.caption(
        "Manual, bounded historical-candle retrieval for local research and backtesting. "
        "This panel does not place orders, access an account, stream live data, or run automatically."
    )

    status = panel.configuration_status
    if status == "configured":
        st.success("Dhan historical-data configuration is available.")
    else:
        st.warning(panel.configuration_message)

    left, middle, right = st.columns(3)
    instrument_id = left.text_input(
        "Dhan canonical instrument ID",
        value="DHAN:NSE_EQ:1333",
        key="dhan_instrument_id",
    )
    interval = middle.selectbox(
        "Interval",
        SUPPORTED_INTERVALS,
        key="dhan_interval",
    )
    end_date = right.date_input(
        "End date (UTC)",
        key="dhan_end_date",
    )
    start_date = st.date_input(
        "Start date (UTC)",
        key="dhan_start_date",
    )

    start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)

    if st.button("Fetch historical candles", key="dhan_fetch_button", disabled=status != "configured"):
        try:
            form = DhanRetrievalForm(
                instrument_id=instrument_id,
                interval=interval,
                start=start,
                end=end,
            )
            result = panel.retrieve(form, retrieved_at=datetime.now(timezone.utc))
        except Exception as exc:
            st.error(f"Dhan historical retrieval failed: {exc}")
        else:
            st.success("Dhan historical dataset retained locally.")
            st.json(result)

    st.caption(
        "Dhan historical data is broker-supplied research data. Its adjustment basis is unadjusted/unknown unless explicitly confirmed; it is not a guarantee of completeness, corporate-action adjustment, or investment suitability."
    )
