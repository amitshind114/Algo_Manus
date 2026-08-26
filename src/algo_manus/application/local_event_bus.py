"""Bounded in-process local event publication for already-retained evidence.

This module deliberately has no network client, message broker, thread, scheduler,
or persistence adapter.  It is an application boundary for local event wiring,
not an external event infrastructure or a source of operational truth.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Callable, Mapping


class LocalEventType(StrEnum):
    """Event types emitted only after their source evidence has been retained."""

    RESEARCH_BATCH_RETAINED = "RESEARCH_BATCH_RETAINED"
    PAPER_LEDGER_EVENT_RETAINED = "PAPER_LEDGER_EVENT_RETAINED"


class LocalEventDeliveryStatus(StrEnum):
    """Read-only status for one synchronous in-process subscriber invocation."""

    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


LocalEventAttribute = str | int | float | bool | None
LocalEventSubscriber = Callable[["LocalApplicationEvent"], None]


@dataclass(frozen=True, slots=True)
class LocalApplicationEvent:
    """Immutable, self-identifying local event that references retained evidence."""

    event_id: str
    event_type: LocalEventType
    occurred_at: datetime
    correlation_id: str
    producer: str
    attributes: Mapping[str, LocalEventAttribute]

    def __post_init__(self) -> None:
        if not self.event_id or not self.correlation_id or not self.producer:
            raise ValueError("local event identity, correlation ID and producer are required")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("local event time must be timezone-aware")
        if not self.attributes:
            raise ValueError("local event attributes are required")
        normalized: dict[str, LocalEventAttribute] = {}
        for key, value in self.attributes.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("local event attribute keys must be non-blank strings")
            if not isinstance(value, (str, int, float, bool, type(None))):
                raise ValueError("local event attributes must be scalar values")
            normalized[key] = value
        object.__setattr__(self, "attributes", MappingProxyType(normalized))

    @classmethod
    def create(
        cls,
        *,
        event_type: LocalEventType,
        occurred_at: datetime,
        correlation_id: str,
        producer: str,
        attributes: Mapping[str, LocalEventAttribute],
    ) -> "LocalApplicationEvent":
        """Create a deterministic local event ID from its immutable content."""

        canonical = json.dumps(
            {
                "event_type": event_type.value,
                "occurred_at": occurred_at.isoformat(),
                "correlation_id": correlation_id,
                "producer": producer,
                "attributes": dict(attributes),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return cls(
            event_id=f"LE-{sha256(canonical.encode()).hexdigest()[:20]}",
            event_type=event_type,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            producer=producer,
            attributes=attributes,
        )


@dataclass(frozen=True, slots=True)
class LocalEventDelivery:
    """Read-only trace of one subscriber invocation in the current process."""

    event_id: str
    subscriber_name: str
    status: LocalEventDeliveryStatus
    failure_type: str | None = None


@dataclass(frozen=True, slots=True)
class LocalEventPublicationResult:
    """Result of one synchronous local publication attempt."""

    event: LocalApplicationEvent
    accepted: bool
    duplicate: bool
    deliveries: tuple[LocalEventDelivery, ...]


@dataclass(frozen=True, slots=True)
class LocalEventBusSnapshot:
    """Display-safe process-local bus metadata; it cannot reconfigure the bus."""

    is_durable: bool
    maximum_retained_events: int
    retained_event_count: int
    retained_delivery_count: int
    subscriber_names: tuple[str, ...]


class LocalEventBus:
    """Synchronous, bounded and subscriber-isolated local event dispatcher.

    Publication happens only after a producer's durable source write succeeds. The
    event trace is intentionally retained in memory only and is empty on restart.
    Subscriber failures are audited locally but never block later subscribers or
    roll back source evidence.
    """

    def __init__(self, *, max_events: int = 1_000, max_deliveries: int | None = None) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be positive")
        retained_deliveries = max_deliveries if max_deliveries is not None else max_events * 10
        if retained_deliveries <= 0:
            raise ValueError("max_deliveries must be positive")
        self._events: deque[LocalApplicationEvent] = deque(maxlen=max_events)
        self._deliveries: deque[LocalEventDelivery] = deque(maxlen=retained_deliveries)
        self._subscribers: dict[str, LocalEventSubscriber] = {}
        self._max_events = max_events

    @property
    def is_durable(self) -> bool:
        """Return false because this audit boundary is deliberately process-local."""

        return False

    def subscribe(self, subscriber_name: str, subscriber: LocalEventSubscriber) -> None:
        """Register one synchronous local subscriber with an explicit stable name."""

        name = subscriber_name.strip()
        if not name:
            raise ValueError("local subscriber name must not be blank")
        if name in self._subscribers:
            raise ValueError("local subscriber name is already registered")
        self._subscribers[name] = subscriber

    def publish(self, event: LocalApplicationEvent) -> LocalEventPublicationResult:
        """Append one in-process event and isolate each subscriber failure."""

        if any(retained.event_id == event.event_id for retained in self._events):
            return LocalEventPublicationResult(event, accepted=False, duplicate=True, deliveries=())
        self._events.append(event)
        deliveries: list[LocalEventDelivery] = []
        for name, subscriber in self._subscribers.items():
            try:
                subscriber(event)
            except Exception as error:  # Subscriber isolation is an explicit local boundary.
                delivery = LocalEventDelivery(event.event_id, name, LocalEventDeliveryStatus.FAILED, type(error).__name__)
            else:
                delivery = LocalEventDelivery(event.event_id, name, LocalEventDeliveryStatus.DELIVERED)
            self._deliveries.append(delivery)
            deliveries.append(delivery)
        return LocalEventPublicationResult(event, accepted=True, duplicate=False, deliveries=tuple(deliveries))

    def events(self, limit: int = 1_000) -> tuple[LocalApplicationEvent, ...]:
        """Return retained current-process events in publication order only."""

        if limit <= 0:
            raise ValueError("limit must be positive")
        return tuple(self._events)[-limit:]

    def deliveries(self, *, event_id: str | None = None, limit: int = 1_000) -> tuple[LocalEventDelivery, ...]:
        """Return retained current-process delivery rows in publication order only."""

        if limit <= 0:
            raise ValueError("limit must be positive")
        rows = tuple(self._deliveries)
        if event_id is not None:
            rows = tuple(row for row in rows if row.event_id == event_id)
        return rows[-limit:]

    def snapshot(self) -> LocalEventBusSnapshot:
        """Return display-safe local wiring metadata without exposing subscribers themselves."""

        return LocalEventBusSnapshot(
            is_durable=False,
            maximum_retained_events=self._max_events,
            retained_event_count=len(self._events),
            retained_delivery_count=len(self._deliveries),
            subscriber_names=tuple(self._subscribers),
        )
