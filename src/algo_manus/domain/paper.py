"""Paper-order state and immutable events for local simulation only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from algo_manus.domain.risk import OrderIntent, RiskDecision
from algo_manus.domain.risk_engine import RiskEngineDecision
from algo_manus.domain.risk import OrderSide


class PaperOrderStatus(StrEnum):
    PENDING_RISK = "PENDING_RISK"
    REJECTED = "REJECTED"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class PaperEventType(StrEnum):
    RISK_DECISION = "RISK_DECISION"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"


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
    """Valid state transitions for one local paper order identity."""

    _TRANSITIONS = {
        (PaperOrderStatus.PENDING_RISK, PaperEventType.ORDER_SUBMITTED): PaperOrderStatus.SUBMITTED,
        (PaperOrderStatus.PENDING_RISK, PaperEventType.ORDER_REJECTED): PaperOrderStatus.REJECTED,
        (PaperOrderStatus.SUBMITTED, PaperEventType.ORDER_FILLED): PaperOrderStatus.FILLED,
        (PaperOrderStatus.SUBMITTED, PaperEventType.ORDER_CANCELLED): PaperOrderStatus.CANCELLED,
    }

    @classmethod
    def apply(cls, current: PaperOrderStatus, event_type: PaperEventType) -> PaperOrderStatus | None:
        """Return the next state or ``None`` when the local event is out of sequence."""

        if event_type is PaperEventType.RISK_DECISION:
            return current
        return cls._TRANSITIONS.get((current, event_type))


@dataclass(frozen=True, slots=True)
class PaperOrder:
    intent: OrderIntent
    status: PaperOrderStatus
    submitted_at: datetime
    filled_at: datetime | None = None
    fill_price: float | None = None


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
