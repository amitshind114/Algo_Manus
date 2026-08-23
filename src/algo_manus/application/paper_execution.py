"""Paper-only order lifecycle applying risk before an explicit simulated fill."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Mapping, Protocol

from algo_manus.domain.paper import (
    PaperEvent,
    PaperEventType,
    PaperOrder,
    PaperOrderStatus,
    PaperSubmission,
)
from algo_manus.domain.risk import (
    DeterministicRiskPolicy,
    OrderIntent,
    PaperPortfolioSnapshot,
    RiskLimits,
)


class PaperLedgerPort(Protocol):
    def append(self, event: PaperEvent) -> None: ...


class PaperExecutionService:
    """Server-side paper workflow. It cannot submit, route or cancel real orders."""

    def __init__(self, policy: DeterministicRiskPolicy, ledger: PaperLedgerPort) -> None:
        self._policy = policy
        self._ledger = ledger

    def submit(
        self,
        *,
        intent: OrderIntent,
        portfolio: PaperPortfolioSnapshot,
        marks: Mapping[str, float],
        limits: RiskLimits,
        kill_switch_active: bool,
        now: datetime | None = None,
    ) -> PaperSubmission:
        occurred_at = now or datetime.now(timezone.utc)
        decision = self._policy.evaluate(
            intent=intent,
            portfolio=portfolio,
            marks=marks,
            limits=limits,
            kill_switch_active=kill_switch_active,
        )
        self._append_event(
            PaperEventType.RISK_DECISION,
            intent,
            occurred_at,
            {"allowed": decision.allowed, "code": decision.code, "reason": decision.reason},
        )
        if not decision.allowed:
            order = PaperOrder(intent=intent, status=PaperOrderStatus.REJECTED, submitted_at=occurred_at)
            self._append_event(PaperEventType.ORDER_REJECTED, intent, occurred_at, {"code": decision.code})
            return PaperSubmission(order=order, decision=decision)

        order = PaperOrder(intent=intent, status=PaperOrderStatus.SUBMITTED, submitted_at=occurred_at)
        self._append_event(PaperEventType.ORDER_SUBMITTED, intent, occurred_at, {"paper_only": True})
        return PaperSubmission(order=order, decision=decision)

    def fill(self, order: PaperOrder, *, fill_price: float, now: datetime | None = None) -> PaperOrder:
        if order.status is not PaperOrderStatus.SUBMITTED:
            raise ValueError("only submitted paper orders can be filled")
        if fill_price <= 0:
            raise ValueError("paper fill price must be positive")
        occurred_at = now or datetime.now(timezone.utc)
        filled = PaperOrder(
            intent=order.intent,
            status=PaperOrderStatus.FILLED,
            submitted_at=order.submitted_at,
            filled_at=occurred_at,
            fill_price=fill_price,
        )
        self._append_event(
            PaperEventType.ORDER_FILLED,
            order.intent,
            occurred_at,
            {"fill_price": fill_price, "quantity": order.intent.quantity, "paper_only": True},
        )
        return filled

    def _append_event(
        self,
        event_type: PaperEventType,
        intent: OrderIntent,
        occurred_at: datetime,
        payload: Mapping[str, object],
    ) -> None:
        canonical = json.dumps(
            {"type": event_type.value, "order": intent.order_id, "time": occurred_at.isoformat(), "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
        )
        self._ledger.append(
            PaperEvent(
                event_id=f"PE-{sha256(canonical.encode()).hexdigest()[:20]}",
                event_type=event_type,
                occurred_at=occurred_at,
                order_id=intent.order_id,
                instrument_id=intent.instrument_id,
                payload=canonical,
            )
        )
