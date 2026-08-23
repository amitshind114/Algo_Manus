"""Deterministic paper-risk contracts with no broker, UI or strategy dependency."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class OrderIntent:
    order_id: str
    instrument_id: str
    side: OrderSide
    quantity: int
    reference_price: float
    strategy_revision_id: str

    def __post_init__(self) -> None:
        if not self.order_id or not self.instrument_id or not self.strategy_revision_id:
            raise ValueError("order, instrument and strategy revision identifiers are required")
        if self.quantity <= 0 or self.reference_price <= 0:
            raise ValueError("quantity and reference_price must be positive")

    @property
    def notional(self) -> float:
        return self.quantity * self.reference_price


@dataclass(frozen=True, slots=True)
class PaperPortfolioSnapshot:
    cash: float
    positions: Mapping[str, int]
    realized_pnl: float
    session_order_count: int

    def position_quantity(self, instrument_id: str) -> int:
        return self.positions.get(instrument_id, 0)

    def gross_notional(self, marks: Mapping[str, float]) -> float:
        return sum(abs(quantity) * marks.get(instrument_id, 0.0) for instrument_id, quantity in self.positions.items())


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_gross_notional: float
    max_notional_per_instrument: float
    max_session_orders: int
    max_daily_loss: float

    def __post_init__(self) -> None:
        if min(
            self.max_gross_notional,
            self.max_notional_per_instrument,
            self.max_session_orders,
            self.max_daily_loss,
        ) <= 0:
            raise ValueError("all risk limits must be positive")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    allowed: bool
    code: str
    reason: str


class DeterministicRiskPolicy:
    """Long-only paper policy. Every accepted intent has an explicit decision."""

    def evaluate(
        self,
        *,
        intent: OrderIntent,
        portfolio: PaperPortfolioSnapshot,
        marks: Mapping[str, float],
        limits: RiskLimits,
        kill_switch_active: bool,
    ) -> RiskDecision:
        if kill_switch_active:
            return RiskDecision(False, "KILL_SWITCH", "paper trading is disabled by the local safety switch")
        if portfolio.session_order_count >= limits.max_session_orders:
            return RiskDecision(False, "SESSION_ORDER_LIMIT", "session order limit has been reached")
        if portfolio.realized_pnl <= -limits.max_daily_loss:
            return RiskDecision(False, "DAILY_LOSS_LIMIT", "daily realized loss limit has been reached")
        if intent.side is OrderSide.SELL and intent.quantity > portfolio.position_quantity(intent.instrument_id):
            return RiskDecision(False, "SHORTING_BLOCKED", "paper MVP does not permit short selling")

        existing = portfolio.position_quantity(intent.instrument_id) * marks.get(
            intent.instrument_id, intent.reference_price
        )
        proposed = existing + (intent.notional if intent.side is OrderSide.BUY else -intent.notional)
        if abs(proposed) > limits.max_notional_per_instrument:
            return RiskDecision(False, "INSTRUMENT_NOTIONAL_LIMIT", "per-instrument notional limit exceeded")
        proposed_gross = portfolio.gross_notional(marks) + (intent.notional if intent.side is OrderSide.BUY else -intent.notional)
        if proposed_gross > limits.max_gross_notional:
            return RiskDecision(False, "GROSS_NOTIONAL_LIMIT", "gross notional limit exceeded")
        if intent.side is OrderSide.BUY and intent.notional > portfolio.cash:
            return RiskDecision(False, "INSUFFICIENT_PAPER_CASH", "paper cash is insufficient for the order")
        return RiskDecision(True, "APPROVED", "paper order is within deterministic risk limits")
