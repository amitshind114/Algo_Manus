from __future__ import annotations

import unittest

from algo_manus.application.paper_risk import PaperPortfolioRiskService
from algo_manus.domain.paper import PaperPortfolioProjection, PaperPositionProjection


class PaperPortfolioRiskTests(unittest.TestCase):
    def test_fixture_marked_snapshot_uses_explicit_marks_and_realized_pnl(self) -> None:
        projection = PaperPortfolioProjection(
            starting_cash=1_000,
            cash=700,
            realized_pnl=-25,
            positions=(PaperPositionProjection("FIXTURE:NSE:EQ:ALPHA", 3, 100),),
            orders=(),
            session_order_count=1,
            unprojectable_event_ids=(),
        )
        snapshot = PaperPortfolioRiskService().snapshot(
            projection,
            marks={"FIXTURE:NSE:EQ:ALPHA": 120},
        )

        self.assertEqual(snapshot.gross_notional, 360)
        self.assertEqual(snapshot.realized_pnl, -25)
        self.assertEqual(snapshot.instrument_notional("FIXTURE:NSE:EQ:ALPHA"), 360)

    def test_missing_mark_fails_closed(self) -> None:
        projection = PaperPortfolioProjection(1_000, 1_000, 0, (PaperPositionProjection("ALPHA", 1, 100),), (), 0, ())
        with self.assertRaisesRegex(ValueError, "explicit positive local mark"):
            PaperPortfolioRiskService().snapshot(projection, marks={})
