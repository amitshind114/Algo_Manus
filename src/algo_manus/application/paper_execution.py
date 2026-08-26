"""Local-only paper-order lifecycle with risk-first immutable event evidence.

No method in this service can call a broker, a venue, a market-price feed, or a
live-execution gateway.  Every operation appends local simulation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Mapping, Protocol

from algo_manus.domain.execution import ReconciliationDisposition
from algo_manus.application.local_event_bus import LocalApplicationEvent, LocalEventBus, LocalEventType
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.paper import (
    LocalLimitFillAssumptions,
    LocalOrderType,
    PaperEvent,
    PaperEventType,
    PaperFillSimulation,
    PaperFillSimulationOutcome,
    PaperOrder,
    PaperOrderLifecycle,
    PaperOrderStatus,
    PaperPromotionEvidence,
    PaperSubmission,
)
from algo_manus.domain.research import DatasetValidationOutcome
from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, PaperPortfolioSnapshot, RiskDecision, RiskLimits
from algo_manus.domain.risk_controls import RiskControlSnapshot
from algo_manus.domain.risk_engine import (
    CentralRiskEngine,
    CentralRiskPolicy,
    PortfolioRiskSnapshot,
    RiskDecisionType,
    RiskEvaluationContext,
)


class PaperLedgerPort(Protocol):
    def append(self, event: PaperEvent) -> None: ...

    def order_ids(self) -> frozenset[str]: ...

    def events_for(self, order_id: str) -> tuple[PaperEvent, ...]: ...


@dataclass(frozen=True, slots=True)
class _RetainedPaperState:
    status: PaperOrderStatus
    filled_quantity: int
    filled_at: datetime | None
    fill_price: float | None
    reconciliation_disposition: ReconciliationDisposition | None


class PaperExecutionService:
    """Risk-gated server-side workflow for simulation only; it cannot route real orders."""

    def __init__(
        self,
        policy: DeterministicRiskPolicy,
        ledger: PaperLedgerPort,
        central_policy: CentralRiskPolicy,
        central_engine: CentralRiskEngine | None = None,
        require_promotion_evidence: bool = False,
        event_bus: LocalEventBus | None = None,
    ) -> None:
        self._policy = policy
        self._ledger = ledger
        self._central_policy = central_policy
        self._central_engine = central_engine or CentralRiskEngine()
        self._require_promotion_evidence = require_promotion_evidence
        self._event_bus = event_bus

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
        portfolio_risk: PortfolioRiskSnapshot | None = None,
        promotion_evidence: PaperPromotionEvidence | None = None,
        control_snapshot: RiskControlSnapshot | None = None,
        now: datetime | None = None,
    ) -> PaperSubmission:
        """Record a local proposal, deterministic risk decision, then acceptance or rejection."""

        occurred_at = now or datetime.now(timezone.utc)
        active_policy = control_snapshot.policy if control_snapshot is not None else self._central_policy
        active_kill_switch = control_snapshot.kill_switch_active if control_snapshot is not None else kill_switch_active
        seen_order_ids = self._ledger.order_ids()
        central_decision = self._central_engine.evaluate(
            intent=intent,
            policy=active_policy,
            context=RiskEvaluationContext(
                kill_switch_active=active_kill_switch,
                seen_order_ids=seen_order_ids,
                open_position_count=sum(1 for quantity in portfolio.positions.values() if quantity != 0),
                instrument_status=instrument_status,
                validation_outcome=validation_outcome,
                portfolio_risk=portfolio_risk,
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
            else RiskDecision(False, f"CENTRAL_{central_decision.decision_type.value}_{central_decision.code.value}", central_decision.reason)
        )
        if self._require_promotion_evidence and promotion_evidence is None:
            decision = RiskDecision(False, "RESEARCH_EVIDENCE_MISSING", "persisted research promotion evidence is required")

        # A duplicate identity must not append a second lifecycle stream to one order ID.
        if intent.order_id in seen_order_ids:
            return PaperSubmission(
                order=PaperOrder(intent=intent, status=PaperOrderStatus.REJECTED, submitted_at=occurred_at),
                decision=decision,
                central_decision=central_decision,
            )

        self._append_event(
            PaperEventType.ORDER_PROPOSED,
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
        self._append_event(
            PaperEventType.RISK_DECISION,
            intent,
            occurred_at,
            {
                "allowed": decision.allowed,
                "code": decision.code,
                "reason": decision.reason,
                "central_policy_version": central_decision.policy_version,
                "central_policy_persisted_at": control_snapshot.policy_persisted_at.isoformat() if control_snapshot is not None else None,
                "kill_switch_change_id": control_snapshot.kill_switch_change.change_id if control_snapshot is not None else None,
                "durable_kill_switch_active": active_kill_switch,
                "central_decision_type": central_decision.decision_type.value,
                "central_decision_code": central_decision.code.value,
                "central_reason": central_decision.reason,
                "research_batch_id": promotion_evidence.batch_id if promotion_evidence is not None else None,
                "research_manifest_id": promotion_evidence.manifest_id if promotion_evidence is not None else None,
                "research_dataset_id": promotion_evidence.dataset_id if promotion_evidence is not None else None,
                "research_validation_policy_version": promotion_evidence.validation_policy_version if promotion_evidence is not None else None,
            },
        )
        if not decision.allowed:
            rejected = PaperOrder(intent=intent, status=PaperOrderStatus.REJECTED, submitted_at=occurred_at)
            self._append_event(
                PaperEventType.ORDER_REJECTED,
                intent,
                occurred_at,
                {"code": decision.code, "side": intent.side.value, "quantity": intent.quantity, "reference_price": intent.reference_price, "paper_only": True},
            )
            return PaperSubmission(order=rejected, decision=decision, central_decision=central_decision)

        accepted = PaperOrder(intent=intent, status=PaperOrderStatus.ACCEPTED, submitted_at=occurred_at)
        self._append_event(
            PaperEventType.ORDER_ACCEPTED,
            intent,
            occurred_at,
            {
                "paper_only": True,
                "risk_event_required": True,
                "side": intent.side.value,
                "quantity": intent.quantity,
                "reference_price": intent.reference_price,
                "strategy_revision_id": intent.strategy_revision_id,
            },
        )
        return PaperSubmission(order=accepted, decision=decision, central_decision=central_decision)

    def work(self, order: PaperOrder, *, now: datetime | None = None) -> PaperOrder:
        """Mark an accepted local proposal as working without contacting an external venue."""

        retained = self._require_actionable(order)
        if retained.status is not PaperOrderStatus.ACCEPTED:
            raise ValueError("only accepted paper orders can become working")
        occurred_at = now or datetime.now(timezone.utc)
        self._append_event(PaperEventType.ORDER_WORKING, order.intent, occurred_at, self._lifecycle_terms(order.intent))
        return PaperOrder(intent=order.intent, status=PaperOrderStatus.WORKING, submitted_at=order.submitted_at)

    def fill(
        self,
        order: PaperOrder,
        *,
        fill_price: float,
        quantity: int | None = None,
        now: datetime | None = None,
    ) -> PaperOrder:
        """Append one bounded local simulated fill and return its immutable order projection."""

        occurred_at = now or datetime.now(timezone.utc)
        return self._record_fill(
            order,
            fill_price=fill_price,
            quantity=quantity,
            occurred_at=occurred_at,
            simulation_evidence=None,
        )

    def simulate_limit_fill(
        self,
        order: PaperOrder,
        *,
        assumptions: LocalLimitFillAssumptions,
        now: datetime | None = None,
    ) -> PaperFillSimulation:
        """Apply declared local limit-fill assumptions without querying any external source.

        This deliberately conservative model uses only the supplied local mark and
        available quantity.  It makes no claim about queue position, venue matching,
        traded volume, broker acceptance or paper-market realism.
        """

        retained = self._require_actionable(order)
        if assumptions.order_type is not LocalOrderType.LIMIT:
            raise ValueError("local simulator accepts limit orders only")
        occurred_at = now or datetime.now(timezone.utc)
        if not assumptions.session_open:
            return self._record_no_fill(order, retained, assumptions, "SESSION_CLOSED", occurred_at)
        if not assumptions.is_limit_eligible(order.intent.side):
            return self._record_no_fill(order, retained, assumptions, "LIMIT_NOT_ELIGIBLE", occurred_at)
        if assumptions.available_quantity == 0:
            return self._record_no_fill(order, retained, assumptions, "NO_AVAILABLE_SIMULATED_VOLUME", occurred_at)

        remaining_quantity = order.intent.quantity - retained.filled_quantity
        fill_quantity = min(remaining_quantity, assumptions.available_quantity)
        outcome = (
            PaperFillSimulationOutcome.FILLED
            if fill_quantity == remaining_quantity
            else PaperFillSimulationOutcome.PARTIAL_FILL
        )
        reason_code = "FILLED_WITH_EXPLICIT_LOCAL_ASSUMPTIONS" if outcome is PaperFillSimulationOutcome.FILLED else "VOLUME_CAPPED"
        evidence = assumptions.event_payload(outcome=outcome, reason_code=reason_code)
        filled = self._record_fill(
            order,
            fill_price=assumptions.effective_fill_price(order.intent.side),
            quantity=fill_quantity,
            occurred_at=occurred_at,
            simulation_evidence=evidence,
        )
        return PaperFillSimulation(filled, outcome, reason_code, assumptions)

    def _record_no_fill(
        self,
        order: PaperOrder,
        retained: _RetainedPaperState,
        assumptions: LocalLimitFillAssumptions,
        reason_code: str,
        occurred_at: datetime,
    ) -> PaperFillSimulation:
        payload = self._lifecycle_terms(order.intent)
        payload.update(
            {
                "cumulative_filled_quantity": retained.filled_quantity,
                "paper_only": True,
                "simulation": assumptions.event_payload(
                    outcome=PaperFillSimulationOutcome.NO_FILL,
                    reason_code=reason_code,
                ),
            }
        )
        self._append_event(PaperEventType.ORDER_UNFILLED, order.intent, occurred_at, payload)
        unchanged = PaperOrder(
            intent=order.intent,
            status=retained.status,
            submitted_at=order.submitted_at,
            filled_at=retained.filled_at,
            fill_price=retained.fill_price,
            filled_quantity=retained.filled_quantity,
        )
        return PaperFillSimulation(unchanged, PaperFillSimulationOutcome.NO_FILL, reason_code, assumptions)

    def _record_fill(
        self,
        order: PaperOrder,
        *,
        fill_price: float,
        quantity: int | None,
        occurred_at: datetime,
        simulation_evidence: Mapping[str, object] | None,
    ) -> PaperOrder:
        """Record one bounded fill; simulation evidence is optional for legacy local calls."""

        retained = self._require_actionable(order)
        if fill_price <= 0:
            raise ValueError("paper fill price must be positive")
        fill_quantity = order.intent.quantity - retained.filled_quantity if quantity is None else quantity
        if fill_quantity <= 0 or fill_quantity > order.intent.quantity - retained.filled_quantity:
            raise ValueError("paper fill quantity must be positive and no greater than the remaining quantity")
        cumulative_quantity = retained.filled_quantity + fill_quantity
        next_status = PaperOrderStatus.FILLED if cumulative_quantity == order.intent.quantity else PaperOrderStatus.PARTIALLY_FILLED
        event_type = PaperEventType.ORDER_FILLED if next_status is PaperOrderStatus.FILLED else PaperEventType.ORDER_PARTIALLY_FILLED
        payload = self._lifecycle_terms(order.intent)
        payload.update(
            {
                "fill_price": fill_price,
                "quantity": fill_quantity,
                "cumulative_filled_quantity": cumulative_quantity,
                "paper_only": True,
            }
        )
        if simulation_evidence is not None:
            payload["simulation"] = dict(simulation_evidence)
        self._append_event(event_type, order.intent, occurred_at, payload)
        return PaperOrder(
            intent=order.intent,
            status=next_status,
            submitted_at=order.submitted_at,
            filled_at=occurred_at,
            fill_price=fill_price,
            filled_quantity=cumulative_quantity,
        )

    def cancel(self, order: PaperOrder, *, reason: str, now: datetime | None = None) -> PaperOrder:
        """Cancel remaining local paper quantity; no external venue or broker is contacted."""

        retained = self._require_actionable(order)
        if not reason.strip():
            raise ValueError("local cancellation reason is required")
        occurred_at = now or datetime.now(timezone.utc)
        payload = self._lifecycle_terms(order.intent)
        payload.update({"reason": reason, "cumulative_filled_quantity": retained.filled_quantity, "paper_only": True})
        self._append_event(PaperEventType.ORDER_CANCELLED, order.intent, occurred_at, payload)
        return PaperOrder(
            intent=order.intent,
            status=PaperOrderStatus.CANCELLED,
            submitted_at=order.submitted_at,
            filled_at=retained.filled_at,
            fill_price=retained.fill_price,
            filled_quantity=retained.filled_quantity,
        )

    def reconcile(
        self,
        order: PaperOrder,
        *,
        disposition: ReconciliationDisposition,
        reason: str,
        now: datetime | None = None,
    ) -> PaperOrder:
        """Append non-destructive local reconciliation evidence for a terminal simulation order."""

        retained = self._retained_state(order)
        if order.status not in {PaperOrderStatus.REJECTED, PaperOrderStatus.FILLED, PaperOrderStatus.CANCELLED} or retained.status is not order.status:
            raise ValueError("only terminal paper orders can be reconciled")
        if not reason.strip():
            raise ValueError("local reconciliation reason is required")
        occurred_at = now or datetime.now(timezone.utc)
        self._append_event(
            PaperEventType.RECONCILIATION_RECORDED,
            order.intent,
            occurred_at,
            {
                "paper_only": True,
                "disposition": disposition.value,
                "reason": reason,
                "cumulative_filled_quantity": retained.filled_quantity,
            },
        )
        return PaperOrder(
            intent=order.intent,
            status=PaperOrderStatus.RECONCILED,
            submitted_at=order.submitted_at,
            filled_at=retained.filled_at,
            fill_price=retained.fill_price,
            filled_quantity=retained.filled_quantity,
            reconciliation_disposition=disposition,
        )

    def _require_actionable(self, order: PaperOrder) -> _RetainedPaperState:
        if order.status not in {PaperOrderStatus.ACCEPTED, PaperOrderStatus.WORKING, PaperOrderStatus.PARTIALLY_FILLED}:
            raise ValueError("paper order is not currently actionable; not currently submitted")
        retained = self._retained_state(order)
        if retained.status is not order.status:
            raise ValueError("paper order is not currently actionable; not currently submitted because retained local lifecycle differs")
        return retained

    def _retained_state(self, order: PaperOrder) -> _RetainedPaperState:
        status = PaperOrderStatus.PENDING_RISK
        filled_quantity = 0
        filled_at: datetime | None = None
        fill_price: float | None = None
        disposition: ReconciliationDisposition | None = None
        risk_seen = False
        for event in self._ledger.events_for(order.intent.order_id):
            payload = self._event_payload(event)
            risk_allowed = payload.get("allowed") if event.event_type is PaperEventType.RISK_DECISION else None
            if event.event_type is PaperEventType.RISK_DECISION:
                if not isinstance(risk_allowed, bool):
                    raise ValueError("stored paper lifecycle is invalid; risk decision evidence is malformed")
                risk_seen = True
            if event.event_type is PaperEventType.ORDER_REJECTED and not risk_seen:
                raise ValueError("stored paper lifecycle is invalid; risk evidence is missing")
            next_status = PaperOrderLifecycle.apply(status, event.event_type, risk_allowed=risk_allowed if isinstance(risk_allowed, bool) else None)
            if next_status is None:
                raise ValueError("stored paper lifecycle is invalid; refusing local transition")
            if event.event_type in {PaperEventType.ORDER_PARTIALLY_FILLED, PaperEventType.ORDER_FILLED}:
                quantity = payload.get("quantity")
                cumulative = payload.get("cumulative_filled_quantity")
                if not isinstance(quantity, int) or quantity <= 0:
                    raise ValueError("stored paper lifecycle is invalid; fill quantity is malformed")
                if cumulative is None and event.event_type is PaperEventType.ORDER_FILLED:
                    cumulative = order.intent.quantity
                if not isinstance(cumulative, int) or cumulative != filled_quantity + quantity or cumulative > order.intent.quantity:
                    raise ValueError("stored paper lifecycle is invalid; cumulative fill evidence is malformed")
                filled_quantity = cumulative
                fill_price_value = payload.get("fill_price")
                if not isinstance(fill_price_value, (int, float)) or fill_price_value <= 0:
                    raise ValueError("stored paper lifecycle is invalid; fill price is malformed")
                fill_price = float(fill_price_value)
                filled_at = event.occurred_at
            if event.event_type is PaperEventType.RECONCILIATION_RECORDED:
                try:
                    disposition = ReconciliationDisposition(payload.get("disposition"))
                except ValueError as error:
                    raise ValueError("stored paper lifecycle is invalid; reconciliation evidence is malformed") from error
            status = next_status
        return _RetainedPaperState(status, filled_quantity, filled_at, fill_price, disposition)

    @staticmethod
    def _event_payload(event: PaperEvent) -> dict[str, object]:
        try:
            payload = json.loads(event.payload).get("payload")
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("stored paper lifecycle is invalid; event payload is malformed") from error
        if not isinstance(payload, dict):
            raise ValueError("stored paper lifecycle is invalid; event payload is malformed")
        return payload

    @staticmethod
    def _lifecycle_terms(intent: OrderIntent) -> dict[str, object]:
        return {"side": intent.side.value, "quantity": intent.quantity, "reference_price": intent.reference_price}

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
        event = PaperEvent(
            event_id=f"PE-{sha256(canonical.encode()).hexdigest()[:20]}",
            event_type=event_type,
            occurred_at=occurred_at,
            order_id=intent.order_id,
            instrument_id=intent.instrument_id,
            payload=canonical,
        )
        self._ledger.append(event)
        if self._event_bus is not None:
            self._event_bus.publish(
                LocalApplicationEvent.create(
                    event_type=LocalEventType.PAPER_LEDGER_EVENT_RETAINED,
                    occurred_at=event.occurred_at,
                    correlation_id=event.order_id,
                    producer="algo_manus.application.paper_execution.PaperExecutionService",
                    attributes={
                        "source_evidence_id": event.event_id,
                        "paper_event_type": event.event_type.value,
                        "instrument_id": event.instrument_id,
                    },
                )
            )
