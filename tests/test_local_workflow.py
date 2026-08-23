from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.application.experiments import BatchBacktestRequest, ExperimentBatchService
from algo_manus.application.instrument_sync import ResearchUniverseService
from algo_manus.application.leaderboard import LeaderboardService, LeaderboardSort
from algo_manus.application.paper_execution import PaperExecutionService
from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.domain.risk import (
    DeterministicRiskPolicy,
    OrderIntent,
    OrderSide,
    PaperPortfolioSnapshot,
    RiskLimits,
)
from algo_manus.domain.strategy import StrategyParameterRevision
from algo_manus.infrastructure.experiments.sqlite_repository import SqliteExperimentBatchRepository
from algo_manus.infrastructure.paper.sqlite_ledger import SqlitePaperLedger
from algo_manus.infrastructure.research import SqliteResearchEvidenceRepository
from algo_manus.strategies.sma_crossover import SmaCrossoverStrategy
from tests.fixtures import snapshot


class LocalWorkflowTests(unittest.TestCase):
    def test_validated_universe_to_experiment_to_risk_gated_paper_fill(self) -> None:
        start = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)
        master = snapshot(downloaded_at=start)
        instrument_id = master.instruments[0].instrument_id
        universe = ResearchUniverseService().create(
            universe_id="single-security-local-check",
            name="Single security local check",
            snapshot=master,
            selected_instrument_ids=(instrument_id,),
        )
        closes = [10, 9, 8, 9, 11, 13, 12, 10, 8]
        dataset = CandleDataset.create(
            instrument_id=instrument_id,
            interval="1d",
            provenance=DataProvenance(
                source_name="fixture-research",
                source_kind=DataSourceKind.FIXTURE,
                source_uri="fixture://local-workflow/candles",
                retrieved_at=start,
                raw_content_sha256=sha256(b"local-workflow-candles").hexdigest(),
                adjustment_basis="unadjusted fixture bars",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=tuple(
                Candle(
                    timestamp=start + timedelta(days=index),
                    open=close - 0.2,
                    high=close + 0.5,
                    low=close - 0.5,
                    close=close,
                    volume=1_000,
                )
                for index, close in enumerate(closes)
            ),
        )
        parameters = StrategyParameterRevision.create(
            "sma_crossover", {"fast_window": 2, "slow_window": 3}
        )

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            experiments = SqliteExperimentBatchRepository(base / "experiments.sqlite3")
            manifests = SqliteResearchEvidenceRepository(base / "research_evidence.sqlite3")
            batch = ExperimentBatchService(BarBacktestService(), experiments, manifests).run(
                request=BatchBacktestRequest(
                    universe_id=universe.universe_id,
                    universe_snapshot_id=universe.snapshot_id,
                    datasets_by_instrument={instrument_id: dataset},
                    initial_cash=1_000,
                    quantity=5,
                    commission_bps=0,
                    slippage_bps=0,
                ),
                strategy=SmaCrossoverStrategy(),
                parameters=parameters,
                created_at=start,
            )
            rows = LeaderboardService().rows(batch, LeaderboardSort.NET_PNL)
            ledger = SqlitePaperLedger(base / "paper.sqlite3")
            submission = PaperExecutionService(DeterministicRiskPolicy(), ledger).submit(
                intent=OrderIntent(
                    order_id="local-workflow-paper-order",
                    instrument_id=instrument_id,
                    side=OrderSide.BUY,
                    quantity=2,
                    reference_price=100,
                    strategy_revision_id=parameters.revision_id,
                ),
                portfolio=PaperPortfolioSnapshot(
                    cash=1_000, positions={}, realized_pnl=0, session_order_count=0
                ),
                marks={instrument_id: 100},
                limits=RiskLimits(
                    max_gross_notional=2_000,
                    max_notional_per_instrument=1_000,
                    max_session_orders=3,
                    max_daily_loss=250,
                ),
                kill_switch_active=False,
                now=start,
            )
            filled = PaperExecutionService(DeterministicRiskPolicy(), ledger).fill(
                submission.order, fill_price=101, now=start
            )

            self.assertEqual(rows[0].instrument_id, instrument_id)
            self.assertIsNotNone(manifests.get(batch.research_manifest_id))
            self.assertTrue(submission.decision.allowed)
            self.assertEqual(filled.fill_price, 101)
            self.assertEqual(len(ledger.events_for("local-workflow-paper-order")), 3)


if __name__ == "__main__":
    unittest.main()
