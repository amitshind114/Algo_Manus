"""Instrument-master synchronization and selected-universe use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from algo_manus.domain.instruments import InstrumentMasterSnapshot, InstrumentStatus
from algo_manus.domain.universe import ResearchUniverse
from algo_manus.infrastructure.instruments.ports import (
    BrokerInstrumentMasterPort,
    InstrumentSnapshotRepository,
)


@dataclass(frozen=True, slots=True)
class SnapshotFreshnessPolicy:
    max_age: timedelta

    def is_fresh(self, checked_at: datetime, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return now - checked_at <= self.max_age


@dataclass(frozen=True, slots=True)
class SyncResult:
    snapshot: InstrumentMasterSnapshot
    downloaded: bool
    reason: str


class InstrumentMasterSyncService:
    """Downloads only through a broker port and persists immutable snapshots.

    The Phase 1 service is intentionally credential-free. A future Angel One
    adapter can implement the port while tests use fixture adapters.
    """

    def __init__(
        self,
        repository: InstrumentSnapshotRepository,
        freshness_policy: SnapshotFreshnessPolicy,
    ) -> None:
        self._repository = repository
        self._freshness_policy = freshness_policy

    def sync_if_stale(
        self,
        provider: BrokerInstrumentMasterPort,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> SyncResult:
        current_time = now or datetime.now(timezone.utc)
        latest = self._repository.latest(provider.broker_name)
        checked_at = self._repository.last_checked_at(provider.broker_name)
        if (
            latest is not None
            and checked_at is not None
            and not force
            and self._freshness_policy.is_fresh(checked_at, current_time)
        ):
            return SyncResult(snapshot=latest, downloaded=False, reason="fresh_snapshot")

        snapshot = provider.download_snapshot(downloaded_at=current_time)
        existing_by_hash = self._repository.find_by_content_hash(
            provider.broker_name, snapshot.content_sha256
        )
        if existing_by_hash is not None:
            self._repository.record_check(
                provider.broker_name, existing_by_hash.snapshot_id, current_time
            )
            return SyncResult(snapshot=existing_by_hash, downloaded=False, reason="unchanged_content")

        self._repository.save(snapshot)
        self._repository.record_check(provider.broker_name, snapshot.snapshot_id, current_time)
        return SyncResult(snapshot=snapshot, downloaded=True, reason="downloaded_new_snapshot")


class ResearchUniverseService:
    """Resolves a selected universe only from active instruments in one snapshot."""

    def create(
        self,
        *,
        universe_id: str,
        name: str,
        snapshot: InstrumentMasterSnapshot,
        selected_instrument_ids: tuple[str, ...],
    ) -> ResearchUniverse:
        by_id = {instrument.instrument_id: instrument for instrument in snapshot.instruments}
        missing = [identity for identity in selected_instrument_ids if identity not in by_id]
        if missing:
            raise ValueError(f"selected instruments are absent from snapshot: {missing}")
        unavailable = [
            identity
            for identity in selected_instrument_ids
            if by_id[identity].status is not InstrumentStatus.ACTIVE
        ]
        if unavailable:
            raise ValueError(f"selected instruments are not active: {unavailable}")
        return ResearchUniverse(
            universe_id=universe_id,
            name=name,
            snapshot_id=snapshot.snapshot_id,
            instrument_ids=selected_instrument_ids,
        )
