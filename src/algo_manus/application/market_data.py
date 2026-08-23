"""Source-policy enforcement and validation before local dataset persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from algo_manus.domain.market_data import CandleDataset, DataSourceKind, DataUseCase
from algo_manus.infrastructure.market_data.ports import CandleDatasetRepository, MarketDataProviderPort


class DataPolicyError(ValueError):
    """Raised when a dataset source is not valid for its requested use."""


@dataclass(frozen=True, slots=True)
class MarketDataRequest:
    instrument_id: str
    interval: str
    start: datetime
    end: datetime
    use_case: DataUseCase

    def __post_init__(self) -> None:
        if not self.instrument_id.strip() or not self.interval.strip():
            raise ValueError("instrument_id and interval are required")
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("request bounds must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("start must be earlier than end")


class MarketDataService:
    """Fetches through a port, enforces source policy and preserves lineage."""

    def __init__(self, repository: CandleDatasetRepository) -> None:
        self._repository = repository

    def ingest(
        self,
        provider: MarketDataProviderPort,
        request: MarketDataRequest,
        *,
        retrieved_at: datetime | None = None,
    ) -> CandleDataset:
        if request.use_case is not DataUseCase.RESEARCH and provider.source_kind is not DataSourceKind.BROKER:
            raise DataPolicyError(
                "paper and risk workflows require a broker-authoritative data provider"
            )
        current_time = retrieved_at or datetime.now(timezone.utc)
        dataset = provider.fetch_candles(
            instrument_id=request.instrument_id,
            interval=request.interval,
            start=request.start,
            end=request.end,
            retrieved_at=current_time,
        )
        if dataset.instrument_id != request.instrument_id or dataset.interval != request.interval:
            raise DataPolicyError("provider dataset does not match requested instrument or interval")
        if dataset.provenance.use_case is not request.use_case:
            raise DataPolicyError("provider provenance use case does not match request")
        if dataset.provenance.source_kind is not provider.source_kind:
            raise DataPolicyError("provider source kind does not match dataset provenance")
        self._repository.save(dataset)
        return dataset
