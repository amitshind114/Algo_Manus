"""Immutable generic execution vocabulary and persistence ports.

These contracts establish a provider-agnostic lifecycle without implementing a
gateway or changing the existing paper-only execution service.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Mapping, Protocol

from algo_manus.domain.risk import OrderIntent, OrderSide


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    RISK_REJECTED = "RISK_REJECTED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    RECONCILED = "RECONCILED"


class ExecutionEventType(StrEnum):
    INTENT_CREATED = "INTENT_CREATED"
    RISK_DECISION = "RISK_DECISION"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_ACKNOWLEDGED = "ORDER_ACKNOWLEDGED"
    FILL_RECORDED = "FILL_RECORDED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_FAILED = "ORDER_FAILED"
    RECONCILIATION_RECORDED = "RECONCILIATION_RECORDED"


class ReconciliationDisposition(StrEnum):
    MATCHED = "MATCHED"
    CORRECTED = "CORRECTED"
    UNRESOLVED = "UNRESOLVED"


class InvalidOrderTransition(ValueError):
    """Raised when a lifecycle status would mutate a terminal/invalid order."""


_ALLOWED_TRANSITIONS: Mapping[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.CREATED: frozenset({OrderStatus.RISK_REJECTED, OrderStatus.SUBMITTED}),
    OrderStatus.RISK_REJECTED: frozenset(),
    OrderStatus.SUBMITTED: frozenset(
        {
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.ACKNOWLEDGED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED}
    ),
    OrderStatus.FILLED: frozenset({OrderStatus.RECONCILED}),
    OrderStatus.CANCELLED: frozenset({OrderStatus.RECONCILED}),
    OrderStatus.REJECTED: frozenset({OrderStatus.RECONCILED}),
    OrderStatus.FAILED: frozenset({OrderStatus.RECONCILED}),
    OrderStatus.RECONCILED: frozenset(),
}


def _require_aware(timestamp: datetime, field_name: str) -> None:
    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Fill:
    """A provider-agnostic immutable fill; it is not a position or P&L record."""

    fill_id: str
    order_id: str
    instrument_id: str
    side: OrderSide
    quantity: int
    price: float
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not self.fill_id.strip() or not self.order_id.strip() or not self.instrument_id.strip():
            raise ValueError("fill, order and instrument identifiers are required")
        if self.quantity <= 0 or self.price <= 0:
            raise ValueError("fill quantity and price must be positive")
        _require_aware(self.occurred_at, "fill occurred_at")


@dataclass(frozen=True, slots=True)
class ExecutionOrder:
    """Immutable lifecycle projection from one intent and zero or more fills."""

    intent: OrderIntent
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    filled_quantity: int = 0

    def __post_init__(self) -> None:
        _require_aware(self.created_at, "order created_at")
        _require_aware(self.updated_at, "order updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("order updated_at cannot predate created_at")
        if self.filled_quantity < 0 or self.filled_quantity > self.intent.quantity:
            raise ValueError("filled_quantity must be within the order quantity")
        if self.status is OrderStatus.FILLED and self.filled_quantity != self.intent.quantity:
            raise ValueError("filled order must have its complete quantity")
        if self.status is OrderStatus.PARTIALLY_FILLED and not 0 < self.filled_quantity < self.intent.quantity:
            raise ValueError("partially filled order needs a partial quantity")
        if self.status in {OrderStatus.CREATED, OrderStatus.RISK_REJECTED, OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED, OrderStatus.REJECTED, OrderStatus.FAILED} and self.filled_quantity != 0:
            raise ValueError("this order state cannot contain fills")

    @classmethod
    def create(cls, intent: OrderIntent, *, created_at: datetime) -> "ExecutionOrder":
        """Create the immutable initial projection for a freshly proposed intent."""

        return cls(intent=intent, status=OrderStatus.CREATED, created_at=created_at, updated_at=created_at)

    @property
    def order_id(self) -> str:
        return self.intent.order_id

    @property
    def remaining_quantity(self) -> int:
        return self.intent.quantity - self.filled_quantity

    def transition(self, status: OrderStatus, *, occurred_at: datetime) -> "ExecutionOrder":
        """Return a new projection only when the requested lifecycle move is valid."""

        _require_aware(occurred_at, "transition occurred_at")
        if occurred_at < self.updated_at:
            raise InvalidOrderTransition("order transition cannot predate current state")
        if status not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidOrderTransition(f"cannot transition {self.status} to {status}")
        return replace(self, status=status, updated_at=occurred_at)

    def record_fill(self, fill: Fill) -> "ExecutionOrder":
        """Return a new fill projection without deriving position or P&L state."""

        if fill.order_id != self.order_id or fill.instrument_id != self.intent.instrument_id:
            raise ValueError("fill must belong to the same order and instrument")
        if fill.side is not self.intent.side:
            raise ValueError("fill side must match order intent side")
        if fill.quantity > self.remaining_quantity:
            raise ValueError("fill quantity exceeds remaining order quantity")
        next_quantity = self.filled_quantity + fill.quantity
        next_status = OrderStatus.FILLED if next_quantity == self.intent.quantity else OrderStatus.PARTIALLY_FILLED
        if fill.occurred_at < self.updated_at:
            raise InvalidOrderTransition("fill cannot predate current order state")
        if next_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidOrderTransition(f"cannot transition {self.status} to {next_status}")
        return replace(
            self,
            status=next_status,
            updated_at=fill.occurred_at,
            filled_quantity=next_quantity,
        )


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """Audit-safe execution event with an explicit causal order reference."""

    event_id: str
    event_type: ExecutionEventType
    occurred_at: datetime
    order_id: str
    instrument_id: str
    correlation_id: str
    payload: Mapping[str, str]

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.event_id, self.order_id, self.instrument_id, self.correlation_id)):
            raise ValueError("execution event identifiers are required")
        _require_aware(self.occurred_at, "event occurred_at")


@dataclass(frozen=True, slots=True)
class ReconciliationRecord:
    """A non-destructive comparison outcome for one local order projection."""

    reconciliation_id: str
    order_id: str
    disposition: ReconciliationDisposition
    reason: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not self.reconciliation_id.strip() or not self.order_id.strip() or not self.reason.strip():
            raise ValueError("reconciliation identifiers and reason are required")
        _require_aware(self.occurred_at, "reconciliation occurred_at")


class OrderRepository(Protocol):
    """Persistence port for immutable order lifecycle projections."""

    def save(self, order: ExecutionOrder) -> None: ...

    def get(self, order_id: str) -> ExecutionOrder | None: ...


class FillRepository(Protocol):
    """Append-only persistence port for fills."""

    def append(self, fill: Fill) -> None: ...

    def for_order(self, order_id: str) -> tuple[Fill, ...]: ...


class ExecutionEventRepository(Protocol):
    """Append-only persistence port for execution/audit events."""

    def append(self, event: ExecutionEvent) -> None: ...

    def for_order(self, order_id: str) -> tuple[ExecutionEvent, ...]: ...


class ReconciliationRepository(Protocol):
    """Persistence port for immutable reconciliation outcomes."""

    def append(self, record: ReconciliationRecord) -> None: ...

    def for_order(self, order_id: str) -> tuple[ReconciliationRecord, ...]: ...
