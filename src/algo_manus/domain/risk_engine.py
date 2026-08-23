"""Central, deterministic and gateway-independent risk-engine contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import OrderIntent, OrderSide


class RiskDecisionType(StrEnum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"
    DEFER = "DEFER"


class RiskDecisionCode(StrEnum):
    APPROVED = "APPROVED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    DUPLICATE_INTENT = "DUPLICATE_INTENT"
    QUANTITY_LIMIT = "QUANTITY_LIMIT"
    NOTIONAL_LIMIT = "NOTIONAL_LIMIT"
    OPEN_POSITION_LIMIT = "OPEN_POSITION_LIMIT"
    INSTRUMENT_CONTEXT_MISSING = "INSTRUMENT_CONTEXT_MISSING"
    INSTRUMENT_NOT_ACTIVE = "INSTRUMENT_NOT_ACTIVE"
    DATA_VALIDATION_MISSING = "DATA_VALIDATION_MISSING"
    DATA_NOT_ACCEPTED = "DATA_NOT_ACCEPTED"
    PORTFOLIO_RISK_CONTEXT_MISSING = "PORTFOLIO_RISK_CONTEXT_MISSING"
    GROSS_EXPOSURE_LIMIT = "GROSS_EXPOSURE_LIMIT"
    INSTRUMENT_EXPOSURE_LIMIT = "INSTRUMENT_EXPOSURE_LIMIT"
    REALIZED_LOSS_LIMIT = "REALIZED_LOSS_LIMIT"
    CONCENTRATION_LIMIT = "CONCENTRATION_LIMIT"


@dataclass(frozen=True, slots=True)
class CentralRiskPolicy:
    """Versioned local policy inputs consumed only by the central risk engine."""

    policy_version: str
    max_quantity_per_order: int
    max_notional_per_order: float
    max_open_positions: int
    max_gross_notional: float | None = None
    max_notional_per_instrument: float | None = None
    max_realized_loss: float | None = None
    max_concentration_pct: float | None = None

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("risk policy version is required")
        if self.max_quantity_per_order <= 0 or self.max_notional_per_order <= 0 or self.max_open_positions <= 0:
            raise ValueError("central risk policy limits must be positive")
        optional_limits = (
            self.max_gross_notional,
            self.max_notional_per_instrument,
            self.max_realized_loss,
        )
        if any(limit is not None and limit <= 0 for limit in optional_limits):
            raise ValueError("configured central portfolio limits must be positive")
        if self.max_concentration_pct is not None and not 0 < self.max_concentration_pct <= 100:
            raise ValueError("configured maximum concentration must be in (0, 100]")

    @property
    def has_portfolio_limits(self) -> bool:
        return any(
            limit is not None
            for limit in (
                self.max_gross_notional,
                self.max_notional_per_instrument,
                self.max_realized_loss,
                self.max_concentration_pct,
            )
        )


@dataclass(frozen=True, slots=True)
class PortfolioRiskSnapshot:
    """Explicitly marked local portfolio facts for one central risk evaluation."""

    gross_notional: float
    realized_pnl: float
    instrument_notionals: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if self.gross_notional < 0:
            raise ValueError("gross_notional cannot be negative")
        if any(not instrument_id or notional < 0 for instrument_id, notional in self.instrument_notionals):
            raise ValueError("instrument risk snapshot entries must be non-empty and non-negative")

    def instrument_notional(self, instrument_id: str) -> float:
        return dict(self.instrument_notionals).get(instrument_id, 0.0)

    def projected_notional(self, intent: OrderIntent) -> float:
        existing = self.instrument_notional(intent.instrument_id)
        return max(0.0, existing + (intent.notional if intent.side is OrderSide.BUY else -intent.notional))

    def projected_gross_notional(self, intent: OrderIntent) -> float:
        return max(0.0, self.gross_notional + (intent.notional if intent.side is OrderSide.BUY else -intent.notional))


@dataclass(frozen=True, slots=True)
class RiskEvaluationContext:
    """Authoritative facts required for a central pre-trade risk decision."""

    kill_switch_active: bool
    seen_order_ids: frozenset[str]
    open_position_count: int
    instrument_status: InstrumentStatus | None
    validation_outcome: DatasetValidationOutcome | None
    portfolio_risk: PortfolioRiskSnapshot | None = None

    def __post_init__(self) -> None:
        if self.open_position_count < 0:
            raise ValueError("open_position_count cannot be negative")


@dataclass(frozen=True, slots=True)
class RiskEngineDecision:
    """Structured, auditable allow/reject/defer outcome from one policy version."""

    decision_type: RiskDecisionType
    code: RiskDecisionCode
    reason: str
    policy_version: str
    order_id: str

    def __post_init__(self) -> None:
        if not self.reason.strip() or not self.policy_version.strip() or not self.order_id.strip():
            raise ValueError("risk decision reason, policy version and order ID are required")

    @property
    def allowed(self) -> bool:
        return self.decision_type is RiskDecisionType.ALLOW


class CentralRiskEngine:
    """Deterministic policy evaluator that fails closed on missing or stale context."""

    def evaluate(
        self,
        *,
        intent: OrderIntent,
        policy: CentralRiskPolicy,
        context: RiskEvaluationContext,
    ) -> RiskEngineDecision:
        if context.kill_switch_active:
            return self._decision(RiskDecisionType.REJECT, RiskDecisionCode.KILL_SWITCH_ACTIVE, "global paper safety switch is active", policy, intent)
        if intent.order_id in context.seen_order_ids:
            return self._decision(RiskDecisionType.REJECT, RiskDecisionCode.DUPLICATE_INTENT, "order intent identity was already evaluated or submitted", policy, intent)
        if context.instrument_status is None:
            return self._decision(RiskDecisionType.DEFER, RiskDecisionCode.INSTRUMENT_CONTEXT_MISSING, "instrument availability context is unavailable", policy, intent)
        if context.instrument_status is not InstrumentStatus.ACTIVE:
            return self._decision(RiskDecisionType.DEFER, RiskDecisionCode.INSTRUMENT_NOT_ACTIVE, f"instrument status is {context.instrument_status.value}", policy, intent)
        if context.validation_outcome is None:
            return self._decision(RiskDecisionType.DEFER, RiskDecisionCode.DATA_VALIDATION_MISSING, "research dataset validation outcome is unavailable", policy, intent)
        if context.validation_outcome.status is not DataValidationStatus.ACCEPTED:
            return self._decision(RiskDecisionType.DEFER, RiskDecisionCode.DATA_NOT_ACCEPTED, f"research dataset validation status is {context.validation_outcome.status.value}", policy, intent)
        if policy.has_portfolio_limits and context.portfolio_risk is None:
            return self._decision(RiskDecisionType.DEFER, RiskDecisionCode.PORTFOLIO_RISK_CONTEXT_MISSING, "portfolio risk snapshot is required by the configured central policy", policy, intent)
        if intent.quantity > policy.max_quantity_per_order:
            return self._decision(RiskDecisionType.REJECT, RiskDecisionCode.QUANTITY_LIMIT, "order quantity exceeds the versioned central risk limit", policy, intent)
        if intent.notional > policy.max_notional_per_order:
            return self._decision(RiskDecisionType.REJECT, RiskDecisionCode.NOTIONAL_LIMIT, "order notional exceeds the versioned central risk limit", policy, intent)
        if context.open_position_count >= policy.max_open_positions:
            return self._decision(RiskDecisionType.REJECT, RiskDecisionCode.OPEN_POSITION_LIMIT, "open position count has reached the versioned central risk limit", policy, intent)
        if context.portfolio_risk is not None:
            portfolio_decision = self._evaluate_portfolio_limits(intent, policy, context.portfolio_risk)
            if portfolio_decision is not None:
                return portfolio_decision
        return self._decision(RiskDecisionType.ALLOW, RiskDecisionCode.APPROVED, "intent satisfies the current central risk policy inputs", policy, intent)

    def _evaluate_portfolio_limits(
        self,
        intent: OrderIntent,
        policy: CentralRiskPolicy,
        snapshot: PortfolioRiskSnapshot,
    ) -> RiskEngineDecision | None:
        projected_gross = snapshot.projected_gross_notional(intent)
        projected_instrument = snapshot.projected_notional(intent)
        if policy.max_gross_notional is not None and projected_gross > policy.max_gross_notional:
            return self._decision(RiskDecisionType.REJECT, RiskDecisionCode.GROSS_EXPOSURE_LIMIT, "projected gross exposure exceeds the versioned central risk limit", policy, intent)
        if policy.max_notional_per_instrument is not None and projected_instrument > policy.max_notional_per_instrument:
            return self._decision(RiskDecisionType.REJECT, RiskDecisionCode.INSTRUMENT_EXPOSURE_LIMIT, "projected instrument exposure exceeds the versioned central risk limit", policy, intent)
        if policy.max_realized_loss is not None and snapshot.realized_pnl <= -policy.max_realized_loss:
            return self._decision(RiskDecisionType.REJECT, RiskDecisionCode.REALIZED_LOSS_LIMIT, "realized local paper loss has reached the versioned central risk limit", policy, intent)
        if policy.max_concentration_pct is not None and projected_gross > 0:
            concentration_pct = (projected_instrument / projected_gross) * 100
            if concentration_pct > policy.max_concentration_pct:
                return self._decision(RiskDecisionType.REJECT, RiskDecisionCode.CONCENTRATION_LIMIT, "projected instrument concentration exceeds the versioned central risk limit", policy, intent)
        return None

    @staticmethod
    def _decision(
        decision_type: RiskDecisionType,
        code: RiskDecisionCode,
        reason: str,
        policy: CentralRiskPolicy,
        intent: OrderIntent,
    ) -> RiskEngineDecision:
        return RiskEngineDecision(decision_type=decision_type, code=code, reason=reason, policy_version=policy.policy_version, order_id=intent.order_id)


class RiskPolicyRepository(Protocol):
    """Future persistence boundary for versioned central risk policies."""

    def save(self, policy: CentralRiskPolicy) -> None: ...

    def get(self, policy_version: str) -> CentralRiskPolicy | None: ...
