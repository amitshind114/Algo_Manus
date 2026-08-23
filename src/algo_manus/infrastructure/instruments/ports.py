"""Infrastructure ports for broker instrument-master integrations."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from algo_manus.domain.instruments import InstrumentMasterSnapshot


class BrokerInstrumentMasterPort(Protocol):
    """A broker adapter that yields a normalized immutable master snapshot.

    Implementations own authentication and network behavior. The application
    layer never receives a raw SDK client or broker credentials.
    """

    @property
    def broker_name(self) -> str: ...

    def download_snapshot(self, *, downloaded_at: datetime) -> InstrumentMasterSnapshot: ...


class InstrumentSnapshotRepository(Protocol):
    """Persistence boundary for immutable master snapshots."""

    def save(self, snapshot: InstrumentMasterSnapshot) -> None: ...

    def latest(self, broker: str) -> InstrumentMasterSnapshot | None: ...

    def find_by_content_hash(self, broker: str, content_sha256: str) -> InstrumentMasterSnapshot | None: ...

    def get(self, snapshot_id: str) -> InstrumentMasterSnapshot | None: ...

    def last_checked_at(self, broker: str) -> datetime | None: ...

    def record_check(self, broker: str, snapshot_id: str, checked_at: datetime) -> None: ...
