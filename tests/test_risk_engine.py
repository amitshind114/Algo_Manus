from __future__ import annotations

from datetime import datetime, timezone
import unittest

from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.research import (
    DataValidationIssue,
    DataValidationSeverity,
    DataValidationStatus,
    DatasetValidationOutcome,
)
from algo_manus.domain.risk import OrderIntent, OrderSide
from algo_manus.domain.risk_engine import (
    CentralRiskEngine,
    CentralRiskPolicy,
    RiskDecisionCode,
    RiskDecisionType,
    RiskEvaluationContext,
)


class CentralRiskEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CentralRiskEngine()
        self.policy = CentralRiskPolicy(
            policy_version="central-risk-v1",
            max_quantity_per_order=100,
            max_notional_per_order=10_000,
            max_open_positions=3,
        )
        self.intent = OrderIntent(
            order_id="risk-intent-1",
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            side=OrderSide.BUY,
            quantity=10,
            reference_price=100.0,
            strategy_revision_id="PARAM-risk",
        )
        self.accepted_validation = DatasetValidationOutcome(
            dataset_id="DATA-risk",
            status=DataValidationStatus.ACCEPTED,
            policy_version="research-dataset-v1",
            validated_at=datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc),
        )

    def _context(self, **overrides) -> RiskEvaluationContext:
        values = {
            "kill_switch_active": False,
            "seen_order_ids": frozenset(),
            "open_position_count": 0,
            "instrument_status": InstrumentStatus.ACTIVE,
            "validation_outcome": self.accepted_validation,
        }
        values.update(overrides)
        return RiskEvaluationContext(**values)

    def test_accepted_context_returns_versioned_allow_decision(self) -> None:
        decision = self.engine.evaluate(intent=self.intent, policy=self.policy, context=self._context())

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_type, RiskDecisionType.ALLOW)
        self.assertEqual(decision.code, RiskDecisionCode.APPROVED)
        self.assertEqual(decision.policy_version, "central-risk-v1")

    def test_engine_rejects_kill_duplicate_quantity_notional_and_open_position_limits(self) -> None:
        scenarios = (
            (self._context(kill_switch_active=True), self.intent, RiskDecisionCode.KILL_SWITCH_ACTIVE),
            (self._context(seen_order_ids=frozenset({self.intent.order_id})), self.intent, RiskDecisionCode.DUPLICATE_INTENT),
            (
                self._context(),
                OrderIntent("quantity-limit", self.intent.instrument_id, OrderSide.BUY, 101, 1.0, "PARAM-risk"),
                RiskDecisionCode.QUANTITY_LIMIT,
            ),
            (
                self._context(),
                OrderIntent("notional-limit", self.intent.instrument_id, OrderSide.BUY, 100, 101.0, "PARAM-risk"),
                RiskDecisionCode.NOTIONAL_LIMIT,
            ),
            (self._context(open_position_count=3), self.intent, RiskDecisionCode.OPEN_POSITION_LIMIT),
        )

        for context, intent, expected_code in scenarios:
            with self.subTest(code=expected_code):
                decision = self.engine.evaluate(intent=intent, policy=self.policy, context=context)
                self.assertEqual(decision.decision_type, RiskDecisionType.REJECT)
                self.assertEqual(decision.code, expected_code)

    def test_engine_defers_when_instrument_or_validation_context_is_missing_or_unaccepted(self) -> None:
        quarantined = DatasetValidationOutcome(
            dataset_id="DATA-risk",
            status=DataValidationStatus.QUARANTINED,
            policy_version="research-dataset-v1",
            validated_at=datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc),
            issues=(
                DataValidationIssue(
                    code="REVIEW_REQUIRED",
                    severity=DataValidationSeverity.WARNING,
                    message="dataset needs manual review",
                ),
            ),
        )
        scenarios = (
            (self._context(instrument_status=None), RiskDecisionCode.INSTRUMENT_CONTEXT_MISSING),
            (self._context(instrument_status=InstrumentStatus.INACTIVE), RiskDecisionCode.INSTRUMENT_NOT_ACTIVE),
            (self._context(validation_outcome=None), RiskDecisionCode.DATA_VALIDATION_MISSING),
            (self._context(validation_outcome=quarantined), RiskDecisionCode.DATA_NOT_ACCEPTED),
        )

        for context, expected_code in scenarios:
            with self.subTest(code=expected_code):
                decision = self.engine.evaluate(intent=self.intent, policy=self.policy, context=context)
                self.assertEqual(decision.decision_type, RiskDecisionType.DEFER)
                self.assertEqual(decision.code, expected_code)


if __name__ == "__main__":
    unittest.main()
