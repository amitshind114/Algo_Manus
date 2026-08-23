"""Central, deterministic and gateway-independent risk-engine contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import OrderIntent


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


@dataclass(frozen=True, slots=True)
class CentralRiskPolicy:
    """Versioned local policy inputs consumed only by the central risk engine."""

    policy_version: str
    max_quantity_per_order: int
    max_notional_per_order: float
    max_open_positions: int

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("risk policy version is required")
        if self.max_quantity_per_order <= 0 or self.max_notional_per_order <= 0 or self.max_open_positions <= 0:
            raise ValueError("central risk policy limits must be positive")


@dataclass(frozen=True, slots=True)
class RiskEvaluationContext:
    """Authoritative facts required for a central pre-trade risk decision."""

    kill_switch_active: bool
    seen_order_ids: frozenset[str]
    open_position_count: int
    instrument_status: InstrumentStatus | None
    validation_outcome: DatasetValidationOutcome | None

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
            return self._decision(
                RiskDecisionType.REJECT,
                RiskDecisionCode.KILL_SWITCH_ACTIVE,
                "global paper safety switch is active",
                policy,
                intent,
            )
        if intent.order_id in context.seen_order_ids:
            return self._decision(
                RiskDecisionType.REJECT,
                RiskDecisionCode.DUPLICATE_INTENT,
                "order intent identity was already evaluated or submitted",
                policy,
                intent,
            )
        if context.instrument_status is None:
            return self._decision(
                RiskDecisionType.DEFER,
                RiskDecisionCode.INSTRUMENT_CONTEXT_MISSING,
                "instrument availability context is unavailable",
                policy,
                intent,
            )
        if context.instrument_status is not InstrumentStatus.ACTIVE:
            return self._decision(
                RiskDecisionType.DEFER,
                RiskDecisionCode.INSTRUMENT_NOT_ACTIVE,
                f"instrument status is {context.instrument_status.value}",
                policy,
                intent,
            )
        if context.validation_outcome is None:
            return self._decision(
                RiskDecisionType.DEFER,
                RiskDecisionCode.DATA_VALIDATION_MISSING,
                "research dataset validation outcome is unavailable",
                policy,
                intent,
            )
        if context.validation_outcome.status is not DataValidationStatus.ACCEPTED:
            return self._decision(
                RiskDecisionType.DEFER,
                RiskDecisionCode.DATA_NOT_ACCEPTED,
                f"research dataset validation status is {context.validation_outcome.status.value}",
                policy,
                intent,
            )
        if intent.quantity > policy.max_quantity_per_order:
            return self._decision(
                RiskDecisionType.REJECT,
                RiskDecisionCode.QUANTITY_LIMIT,
                "order quantity exceeds the versioned central risk limit",
                policy,
                intent,
            )
        if intent.notional > policy.max_notional_per_order:
            return self._decision(
                RiskDecisionType.REJECT,
                RiskDecisionCode.NOTIONAL_LIMIT,
                "order notional exceeds the versioned central risk limit",
                policy,
                intent,
            )
        if context.open_position_count >= policy.max_open_positions:
            return self._decision(
                RiskDecisionType.REJECT,
                RiskDecisionCode.OPEN_POSITION_LIMIT,
                "open position count has reached the versioned central risk limit",
                policy,
                intent,
            )
        return self._decision(
            RiskDecisionType.ALLOW,
            RiskDecisionCode.APPROVED,
            "intent satisfies the current central risk policy inputs",
            policy,
            intent,
        )

    @staticmethod
    def _decision(
        decision_type: RiskDecisionType,
        code: RiskDecisionCode,
        reason: str,
        policy: CentralRiskPolicy,
        intent: OrderIntent,
    ) -> RiskEngineDecision:
        return RiskEngineDecision(
            decision_type=decision_type,
            code=code,
            reason=reason,
            policy_version=policy.policy_version,
            order_id=intent.order_id,
        )


class RiskPolicyRepository(Protocol):
    """Future persistence boundary for versioned central risk policies."""

    def save(self, policy: CentralRiskPolicy) -> None: ...

    def get(self, policy_version: str) -> CentralRiskPolicy | None: ...
