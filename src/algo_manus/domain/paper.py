"""Paper-order state and immutable events for local simulation only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from algo_manus.domain.execution import ReconciliationDisposition
from algo_manus.domain.risk import OrderIntent, RiskDecision
from algo_manus.domain.risk_engine import RiskEngineDecision
from algo_manus.domain.risk import OrderSide


class PaperOrderStatus(StrEnum):
    PENDING_RISK = "PENDING_RISK"
    RISK_APPROVED = "RISK_APPROVED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"
    SUBMITTED = "ACCEPTED"  # Backward-compatible alias for prior local projections.
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    RECONCILED = "RECONCILED"


class PaperEventType(StrEnum):
    ORDER_PROPOSED = "ORDER_PROPOSED"
    RISK_DECISION = "RISK_DECISION"
    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"  # Legacy retained-event compatibility only.
    ORDER_WORKING = "ORDER_WORKING"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    RECONCILIATION_RECORDED = "RECONCILIATION_RECORDED"


@dataclass(frozen=True, slots=True)
class PaperPromotionEvidence:
    """Immutable references proving that one local paper proposal came from research evidence."""

    batch_id: str
    manifest_id: str
    dataset_id: str
    validation_policy_version: str

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (self.batch_id, self.manifest_id, self.dataset_id, self.validation_policy_version)
        ):
            raise ValueError("paper promotion evidence identifiers are required")


class PaperOrderLifecycle:
    """Valid state transitions for one immutable local paper-event stream."""

    _TRANSITIONS = {
        (PaperOrderStatus.PENDING_RISK, PaperEventType.ORDER_PROPOSED): PaperOrderStatus.PENDING_RISK,
        (PaperOrderStatus.PENDING_RISK, PaperEventType.ORDER_REJECTED): PaperOrderStatus.REJECTED,
        (PaperOrderStatus.RISK_APPROVED, PaperEventType.ORDER_ACCEPTED): PaperOrderStatus.ACCEPTED,
        (PaperOrderStatus.RISK_APPROVED, PaperEventType.ORDER_SUBMITTED): PaperOrderStatus.ACCEPTED,
        (PaperOrderStatus.ACCEPTED, PaperEventType.ORDER_WORKING): PaperOrderStatus.WORKING,
        (PaperOrderStatus.ACCEPTED, PaperEventType.ORDER_PARTIALLY_FILLED): PaperOrderStatus.PARTIALLY_FILLED,
        (PaperOrderStatus.ACCEPTED, PaperEventType.ORDER_FILLED): PaperOrderStatus.FILLED,
        (PaperOrderStatus.ACCEPTED, PaperEventType.ORDER_CANCELLED): PaperOrderStatus.CANCELLED,
        (PaperOrderStatus.WORKING, PaperEventType.ORDER_PARTIALLY_FILLED): PaperOrderStatus.PARTIALLY_FILLED,
        (PaperOrderStatus.WORKING, PaperEventType.ORDER_FILLED): PaperOrderStatus.FILLED,
        (PaperOrderStatus.WORKING, PaperEventType.ORDER_CANCELLED): PaperOrderStatus.CANCELLED,
        (PaperOrderStatus.PARTIALLY_FILLED, PaperEventType.ORDER_PARTIALLY_FILLED): PaperOrderStatus.PARTIALLY_FILLED,
        (PaperOrderStatus.PARTIALLY_FILLED, PaperEventType.ORDER_FILLED): PaperOrderStatus.FILLED,
        (PaperOrderStatus.PARTIALLY_FILLED, PaperEventType.ORDER_CANCELLED): PaperOrderStatus.CANCELLED,
        (PaperOrderStatus.REJECTED, PaperEventType.RECONCILIATION_RECORDED): PaperOrderStatus.RECONCILED,
        (PaperOrderStatus.FILLED, PaperEventType.RECONCILIATION_RECORDED): PaperOrderStatus.RECONCILED,
        (PaperOrderStatus.CANCELLED, PaperEventType.RECONCILIATION_RECORDED): PaperOrderStatus.RECONCILED,
    }

    @classmethod
    def apply(
        cls,
        current: PaperOrderStatus,
        event_type: PaperEventType,
        *,
        risk_allowed: bool | None = None,
    ) -> PaperOrderStatus | None:
        """Return the next state, or ``None`` when retained evidence is out of sequence."""

        if event_type is PaperEventType.RISK_DECISION:
            if current is not PaperOrderStatus.PENDING_RISK:
                return None
            return PaperOrderStatus.RISK_APPROVED if risk_allowed is True else PaperOrderStatus.PENDING_RISK
        return cls._TRANSITIONS.get((current, event_type))


@dataclass(frozen=True, slots=True)
class PaperOrder:
    intent: OrderIntent
    status: PaperOrderStatus
    submitted_at: datetime
    filled_at: datetime | None = None
    fill_price: float | None = None
    filled_quantity: int = 0
    reconciliation_disposition: ReconciliationDisposition | None = None

    @property
    def remaining_quantity(self) -> int:
        return self.intent.quantity - self.filled_quantity


@dataclass(frozen=True, slots=True)
class PaperEvent:
    event_id: str
    event_type: PaperEventType
    occurred_at: datetime
    order_id: str
    instrument_id: str
    payload: str


@dataclass(frozen=True, slots=True)
class PaperSubmission:
    order: PaperOrder
    decision: RiskDecision
    central_decision: RiskEngineDecision | None = None


@dataclass(frozen=True, slots=True)
class PaperPositionProjection:
    """Derived local position state from replayable paper fill events."""

    instrument_id: str
    quantity: int
    average_entry_price: float


@dataclass(frozen=True, slots=True)
class PaperOrderProjection:
    """Derived local order state; never an external order acknowledgement."""

    order_id: str
    instrument_id: str
    side: OrderSide | None
    quantity: int | None
    status: PaperOrderStatus
    submitted_at: datetime | None
    filled_at: datetime | None
    fill_price: float | None
    filled_quantity: int
    remaining_quantity: int | None
    reconciliation_disposition: ReconciliationDisposition | None


@dataclass(frozen=True, slots=True)
class PaperPortfolioProjection:
    """Deterministic, local-only replay result using an explicit starting cash balance."""

    starting_cash: float
    cash: float
    realized_pnl: float
    positions: tuple[PaperPositionProjection, ...]
    orders: tuple[PaperOrderProjection, ...]
    session_order_count: int
    unprojectable_event_ids: tuple[str, ...]
