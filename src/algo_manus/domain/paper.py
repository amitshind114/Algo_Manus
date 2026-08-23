"""Paper-order state and immutable events for local simulation only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from algo_manus.domain.risk import OrderIntent, RiskDecision
from algo_manus.domain.risk_engine import RiskEngineDecision


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
