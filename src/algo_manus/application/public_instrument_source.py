"""Read-only local status and manual sync use case for public broker masters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from algo_manus.application.instrument_sync import (
    InstrumentMasterSyncService,
    SnapshotFreshnessPolicy,
    SyncResult,
)
from algo_manus.domain.instruments import Instrument, InstrumentMasterSnapshot
from algo_manus.infrastructure.instruments.ports import (
    BrokerInstrumentMasterPort,
    InstrumentSnapshotRepository,
)


@dataclass(frozen=True, slots=True)
class PublicInstrumentSourceStatus:
    """Display-safe status of one locally retained broker master source."""

    broker_name: str
    availability: str
    snapshot_id: str | None
    source_uri: str | None
    content_sha256: str | None
    instrument_count: int
    downloaded_at: datetime | None
    last_checked_at: datetime | None
    manual_sync_required: bool


class PublicInstrumentSourceService:
    """Coordinates only explicit public-master downloads and local evidence.

    The service never invokes itself in the background and cannot authenticate,
    inspect an account, retrieve price data, place orders or alter research and
    paper records.  The caller must invoke :meth:`sync` explicitly.
    """

    def __init__(
        self,
        repository: InstrumentSnapshotRepository,
        provider: BrokerInstrumentMasterPort,
        *,
        freshness: timedelta = timedelta(hours=24),
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._sync = InstrumentMasterSyncService(
            repository, SnapshotFreshnessPolicy(max_age=freshness)
        )

    def status(self) -> PublicInstrumentSourceStatus:
        latest = self._repository.latest(self._provider.broker_name)
        checked_at = self._repository.last_checked_at(self._provider.broker_name)
        if latest is None:
            return PublicInstrumentSourceStatus(
                broker_name=self._provider.broker_name,
                availability="not_downloaded",
                snapshot_id=None,
                source_uri=None,
                content_sha256=None,
                instrument_count=0,
                downloaded_at=None,
                last_checked_at=checked_at,
                manual_sync_required=True,
            )
        return PublicInstrumentSourceStatus(
            broker_name=self._provider.broker_name,
            availability="available",
            snapshot_id=latest.snapshot_id,
            source_uri=latest.source_uri,
            content_sha256=latest.content_sha256,
            instrument_count=len(latest.instruments),
            downloaded_at=latest.downloaded_at,
            last_checked_at=checked_at,
            manual_sync_required=False,
        )

    def latest_snapshot(self) -> InstrumentMasterSnapshot | None:
        """Return retained public-master evidence only; this never triggers a download."""

        return self._repository.latest(self._provider.broker_name)

    def preview(self, *, limit: int = 100) -> tuple[Instrument, ...]:
        """Return a bounded retained snapshot preview without altering the source."""

        if limit <= 0:
            raise ValueError("limit must be positive")
        snapshot = self.latest_snapshot()
        return snapshot.instruments[:limit] if snapshot is not None else ()

    def sync(self, *, now: datetime | None = None, force: bool = True) -> SyncResult:
        """Perform one user-invoked download; defaulting to force preserves manual intent."""

        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return self._sync.sync_if_stale(
            self._provider,
            now=current_time,
            force=force,
        )
