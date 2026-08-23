from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.paper_execution import PaperExecutionService
from algo_manus.application.paper_projection import PaperOperationsReadService
from algo_manus.domain.instruments import InstrumentStatus
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome
from algo_manus.domain.risk import DeterministicRiskPolicy, OrderIntent, OrderSide, PaperPortfolioSnapshot, RiskLimits
from algo_manus.domain.risk_engine import CentralRiskPolicy
from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger


class PaperProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 23, 10, 30, tzinfo=timezone.utc)
        self.instrument_id = "FIXTURE:NSE:EQ:ALPHA"
        self.policy = CentralRiskPolicy("projection-risk-v1", 100, 10_000, 3)
        self.limits = RiskLimits(5_000, 2_000, 5, 500)
        self.validation = DatasetValidationOutcome(
            dataset_id="DATA-projection",
            status=DataValidationStatus.ACCEPTED,
            policy_version="research-dataset-v1",
            validated_at=self.now,
        )

    def _submit_and_fill(self, service, intent, portfolio, fill_price: float) -> None:
        submitted = service.submit(
            intent=intent,
            portfolio=portfolio,
            marks={self.instrument_id: intent.reference_price},
            limits=self.limits,
            kill_switch_active=False,
            instrument_status=InstrumentStatus.ACTIVE,
            validation_outcome=self.validation,
            now=self.now,
        )
        self.assertTrue(submitted.decision.allowed)
        service.fill(submitted.order, fill_price=fill_price, now=self.now)

    def test_replay_survives_restart_and_derives_cash_positions_pnl_and_orders(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite"
            ledger = SqlitePaperLedger(path)
            service = PaperExecutionService(DeterministicRiskPolicy(), ledger, self.policy)
            self._submit_and_fill(
                service,
                OrderIntent("projection-buy", self.instrument_id, OrderSide.BUY, 10, 100, "PARAM-projection"),
                PaperPortfolioSnapshot(2_000, {}, 0, 0),
                110,
            )
            self._submit_and_fill(
                service,
                OrderIntent("projection-sell", self.instrument_id, OrderSide.SELL, 4, 120, "PARAM-projection"),
                PaperPortfolioSnapshot(900, {self.instrument_id: 10}, 0, 1),
                120,
            )

            restarted = PaperOperationsReadService(SqlitePaperLedger(path))
            projection = restarted.portfolio(starting_cash=2_000)

            self.assertEqual(len(restarted.events()), 6)
            self.assertEqual(projection.cash, 1_380)
            self.assertEqual(projection.realized_pnl, 40)
            self.assertEqual(projection.positions[0].quantity, 6)
            self.assertEqual(projection.positions[0].average_entry_price, 110)
            self.assertEqual(projection.session_order_count, 2)
            self.assertFalse(projection.unprojectable_event_ids)

    def test_replay_marks_old_or_malformed_fill_evidence_as_unprojectable(self) -> None:
        with TemporaryDirectory() as directory:
            ledger = SqlitePaperLedger(Path(directory) / "paper.sqlite")
            from algo_manus.domain.paper import PaperEvent, PaperEventType

            ledger.append(
                PaperEvent(
                    event_id="legacy-fill",
                    event_type=PaperEventType.ORDER_FILLED,
                    occurred_at=self.now,
                    order_id="legacy-order",
                    instrument_id=self.instrument_id,
                    payload='{"payload":{"fill_price":100}}',
                )
            )
            projection = PaperOperationsReadService(ledger).portfolio(starting_cash=1_000)

            self.assertEqual(projection.cash, 1_000)
            self.assertEqual(projection.unprojectable_event_ids, ("legacy-fill",))


if __name__ == "__main__":
    unittest.main()
