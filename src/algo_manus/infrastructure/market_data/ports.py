"""Ports separating market-data policy from provider-specific transport."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from algo_manus.domain.market_data import CandleDataset, DataSourceKind


class MarketDataProviderPort(Protocol):
    """A provider adapter returning normalized candle datasets.

    Phase 2 has no live implementation. A future broker adapter owns its SDK,
    authentication and network calls while this application contract remains pure.
    """

    @property
    def source_name(self) -> str: ...

    @property
    def source_kind(self) -> DataSourceKind: ...

    def fetch_candles(
        self,
        *,
        instrument_id: str,
        interval: str,
        start: datetime,
        end: datetime,
        retrieved_at: datetime,
    ) -> CandleDataset: ...


class CandleDatasetRepository(Protocol):
    """Persistence boundary for immutable accepted datasets."""

    def save(self, dataset: CandleDataset) -> None: ...

    def get(self, dataset_id: str) -> CandleDataset | None: ...

    def latest(self, *, source_name: str) -> CandleDataset | None: ...
