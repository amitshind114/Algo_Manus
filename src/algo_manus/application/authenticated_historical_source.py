"""Manual read-only use case for authenticated broker historical candles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from algo_manus.application.market_data import MarketDataRequest, MarketDataService
from algo_manus.domain.market_data import Candle, CandleDataset, DataUseCase
from algo_manus.infrastructure.market_data.ports import CandleDatasetRepository, MarketDataProviderPort


@dataclass(frozen=True, slots=True)
class AuthenticatedHistoricalSourceStatus:
    """Display-safe local evidence and configuration status for Option B."""

    source_name: str
    availability: str
    credentials_configured: bool
    dataset_id: str | None
    instrument_id: str | None
    interval: str | None
    candle_count: int
    retrieved_at: datetime | None
    source_uri: str | None
    content_sha256: str | None
    manual_sync_required: bool


class AuthenticatedHistoricalCandleService:
    """Coordinates one explicit research-only authenticated candle retrieval.

    This service does not create, refresh or persist a broker session.  It never
    calls account, position, order, price-feed or WebSocket endpoints and does
    not schedule background work.  It saves only successful research datasets
    through the existing immutable repository boundary.
    """

    def __init__(self, repository: CandleDatasetRepository, provider: MarketDataProviderPort) -> None:
        self._repository = repository
        self._provider = provider
        self._market_data = MarketDataService(repository)

    def status(self) -> AuthenticatedHistoricalSourceStatus:
        latest = self._repository.latest(source_name=self._provider.source_name)
        configured = bool(getattr(self._provider, "credentials_configured", False))
        if latest is None:
            return AuthenticatedHistoricalSourceStatus(
                source_name=self._provider.source_name,
                availability="not_downloaded" if configured else "local_configuration_required",
                credentials_configured=configured,
                dataset_id=None,
                instrument_id=None,
                interval=None,
                candle_count=0,
                retrieved_at=None,
                source_uri=None,
                content_sha256=None,
                manual_sync_required=True,
            )
        return AuthenticatedHistoricalSourceStatus(
            source_name=self._provider.source_name,
            availability="available",
            credentials_configured=configured,
            dataset_id=latest.dataset_id,
            instrument_id=latest.instrument_id,
            interval=latest.interval,
            candle_count=len(latest.candles),
            retrieved_at=latest.provenance.retrieved_at,
            source_uri=latest.provenance.source_uri,
            content_sha256=latest.provenance.raw_content_sha256,
            manual_sync_required=not configured,
        )

    def latest_dataset(self) -> CandleDataset | None:
        """Read retained local evidence only; this never performs a broker request."""

        return self._repository.latest(source_name=self._provider.source_name)

    def preview(self, *, limit: int = 100) -> tuple[Candle, ...]:
        """Return a bounded retained local candle sample without refreshing data."""

        if limit <= 0:
            raise ValueError("limit must be positive")
        dataset = self.latest_dataset()
        return dataset.candles[:limit] if dataset is not None else ()

    def sync(self, request: MarketDataRequest, *, now: datetime | None = None) -> CandleDataset:
        """Perform one caller-invoked research retrieval and immutable persistence."""

        if request.use_case is not DataUseCase.RESEARCH:
            raise ValueError("authenticated historical ingestion is research-only in Option B")
        if not bool(getattr(self._provider, "credentials_configured", False)):
            raise ValueError("local read-only configuration is required before a manual candle request")
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return self._market_data.ingest(self._provider, request, retrieved_at=current_time)
