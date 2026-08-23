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
    PaperOrderLifecycle,
    PaperOrderStatus,
    PaperSubmission,
)
from algo_manus.domain.risk import (
    DeterministicRiskPolicy,
    OrderIntent,
    PaperPortfolioSnapshot,
    RiskDecision,
    RiskLimits,
)
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.research import DatasetValidationOutcome
from algo_manus.domain.risk_controls import RiskControlSnapshot
from algo_manus.domain.risk_engine import (
    CentralRiskEngine,
    CentralRiskPolicy,
    RiskDecisionType,
    RiskEvaluationContext,
)


class PaperLedgerPort(Protocol):
    def append(self, event: PaperEvent) -> None: ...

    def order_ids(self) -> frozenset[str]: ...

    def events_for(self, order_id: str) -> tuple[PaperEvent, ...]: ...


class PaperExecutionService:
    """Server-side paper workflow. It cannot submit, route or cancel real orders."""

    def __init__(
        self,
        policy: DeterministicRiskPolicy,
        ledger: PaperLedgerPort,
        central_policy: CentralRiskPolicy,
        central_engine: CentralRiskEngine | None = None,
    ) -> None:
        self._policy = policy
        self._ledger = ledger
        self._central_policy = central_policy
        self._central_engine = central_engine or CentralRiskEngine()

    def submit(
        self,
        *,
        intent: OrderIntent,
        portfolio: PaperPortfolioSnapshot,
        marks: Mapping[str, float],
        limits: RiskLimits,
        kill_switch_active: bool,
        instrument_status: InstrumentStatus | None,
        validation_outcome: DatasetValidationOutcome | None,
        control_snapshot: RiskControlSnapshot | None = None,
        now: datetime | None = None,
    ) -> PaperSubmission:
        occurred_at = now or datetime.now(timezone.utc)
        active_policy = control_snapshot.policy if control_snapshot is not None else self._central_policy
        active_kill_switch = (
            control_snapshot.kill_switch_active if control_snapshot is not None else kill_switch_active
        )
        central_decision = self._central_engine.evaluate(
            intent=intent,
            policy=active_policy,
            context=RiskEvaluationContext(
                kill_switch_active=active_kill_switch,
                seen_order_ids=self._ledger.order_ids(),
                open_position_count=sum(1 for quantity in portfolio.positions.values() if quantity != 0),
                instrument_status=instrument_status,
                validation_outcome=validation_outcome,
            ),
        )
        decision = (
            self._policy.evaluate(
                intent=intent,
                portfolio=portfolio,
                marks=marks,
                limits=limits,
                kill_switch_active=active_kill_switch,
            )
            if central_decision.decision_type is RiskDecisionType.ALLOW
            else RiskDecision(
                False,
                f"CENTRAL_{central_decision.decision_type.value}_{central_decision.code.value}",
                central_decision.reason,
            )
        )
        self._append_event(
            PaperEventType.RISK_DECISION,
            intent,
            occurred_at,
            {
                "allowed": decision.allowed,
                "code": decision.code,
                "reason": decision.reason,
                "central_policy_version": central_decision.policy_version,
                "central_policy_persisted_at": (
                    control_snapshot.policy_persisted_at.isoformat() if control_snapshot is not None else None
                ),
                "kill_switch_change_id": (
                    control_snapshot.kill_switch_change.change_id if control_snapshot is not None else None
                ),
                "durable_kill_switch_active": active_kill_switch,
                "central_decision_type": central_decision.decision_type.value,
                "central_decision_code": central_decision.code.value,
                "central_reason": central_decision.reason,
            },
        )
        if not decision.allowed:
            order = PaperOrder(intent=intent, status=PaperOrderStatus.REJECTED, submitted_at=occurred_at)
            self._append_event(
                PaperEventType.ORDER_REJECTED,
                intent,
                occurred_at,
                {
                    "code": decision.code,
                    "side": intent.side.value,
                    "quantity": intent.quantity,
                    "reference_price": intent.reference_price,
                },
            )
            return PaperSubmission(order=order, decision=decision, central_decision=central_decision)

        order = PaperOrder(intent=intent, status=PaperOrderStatus.SUBMITTED, submitted_at=occurred_at)
        self._append_event(
            PaperEventType.ORDER_SUBMITTED,
            intent,
            occurred_at,
            {
                "paper_only": True,
                "side": intent.side.value,
                "quantity": intent.quantity,
                "reference_price": intent.reference_price,
                "strategy_revision_id": intent.strategy_revision_id,
            },
        )
        return PaperSubmission(order=order, decision=decision, central_decision=central_decision)

    def fill(self, order: PaperOrder, *, fill_price: float, now: datetime | None = None) -> PaperOrder:
        self._require_submitted(order)
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
            {
                "fill_price": fill_price,
                "quantity": order.intent.quantity,
                "side": order.intent.side.value,
                "reference_price": order.intent.reference_price,
                "paper_only": True,
            },
        )
        return filled

    def cancel(self, order: PaperOrder, *, reason: str, now: datetime | None = None) -> PaperOrder:
        """Cancel one still-submitted local paper order; it cannot contact an external venue."""

        self._require_submitted(order)
        if not reason.strip():
            raise ValueError("local cancellation reason is required")
        occurred_at = now or datetime.now(timezone.utc)
        cancelled = PaperOrder(intent=order.intent, status=PaperOrderStatus.CANCELLED, submitted_at=order.submitted_at)
        self._append_event(
            PaperEventType.ORDER_CANCELLED,
            order.intent,
            occurred_at,
            {
                "reason": reason,
                "side": order.intent.side.value,
                "quantity": order.intent.quantity,
                "reference_price": order.intent.reference_price,
                "paper_only": True,
            },
        )
        return cancelled

    def _require_submitted(self, order: PaperOrder) -> None:
        if order.status is not PaperOrderStatus.SUBMITTED:
            raise ValueError("only submitted paper orders can transition")
        status = PaperOrderStatus.PENDING_RISK
        for event in self._ledger.events_for(order.intent.order_id):
            next_status = PaperOrderLifecycle.apply(status, event.event_type)
            if next_status is None:
                raise ValueError("stored paper lifecycle is invalid; refusing local transition")
            status = next_status
        if status is not PaperOrderStatus.SUBMITTED:
            raise ValueError("paper order is not currently submitted; duplicate or terminal transition blocked")

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
