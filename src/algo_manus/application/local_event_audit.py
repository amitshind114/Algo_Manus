"""Read-only audit projection for the bounded process-local event bus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from algo_manus.application.local_event_bus import (
    LocalApplicationEvent,
    LocalEventBusSnapshot,
    LocalEventDelivery,
    LocalEventDeliveryStatus,
)


class LocalEventAuditPort(Protocol):
    def events(self, limit: int = 1_000) -> tuple[LocalApplicationEvent, ...]: ...

    def deliveries(self, *, event_id: str | None = None, limit: int = 1_000) -> tuple[LocalEventDelivery, ...]: ...

    def snapshot(self) -> LocalEventBusSnapshot: ...


@dataclass(frozen=True, slots=True)
class LocalEventWiringAuditRow:
    """Display-safe event and delivery totals for one current-process event."""

    event_id: str
    occurred_at: datetime
    event_type: str
    correlation_id: str
    producer: str
    source_evidence_id: str | None
    delivered_subscriber_count: int
    failed_subscriber_count: int


class LocalEventWiringAuditReadService:
    """Read current-process local wiring evidence only; it cannot publish or subscribe."""

    def __init__(self, bus: LocalEventAuditPort) -> None:
        self._bus = bus

    def rows(self, limit: int = 1_000) -> tuple[LocalEventWiringAuditRow, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        rows: list[LocalEventWiringAuditRow] = []
        for event in self._bus.events(limit):
            deliveries = self._bus.deliveries(event_id=event.event_id, limit=limit)
            rows.append(
                LocalEventWiringAuditRow(
                    event_id=event.event_id,
                    occurred_at=event.occurred_at,
                    event_type=event.event_type.value,
                    correlation_id=event.correlation_id,
                    producer=event.producer,
                    source_evidence_id=self._source_evidence_id(event),
                    delivered_subscriber_count=sum(
                        item.status is LocalEventDeliveryStatus.DELIVERED for item in deliveries
                    ),
                    failed_subscriber_count=sum(
                        item.status is LocalEventDeliveryStatus.FAILED for item in deliveries
                    ),
                )
            )
        return tuple(rows)

    def snapshot(self) -> LocalEventBusSnapshot:
        """Return the safe bus-boundary summary without exposing mutable subscribers."""

        return self._bus.snapshot()

    @staticmethod
    def _source_evidence_id(event: LocalApplicationEvent) -> str | None:
        value = event.attributes.get("source_evidence_id")
        return value if isinstance(value, str) and value else None
