"""Fixture-marked local portfolio-risk snapshots derived from durable paper replay."""

from __future__ import annotations

from typing import Mapping

from algo_manus.domain.paper import PaperPortfolioProjection
from algo_manus.domain.risk_engine import PortfolioRiskSnapshot


class PaperPortfolioRiskService:
    """Converts a local replay plus explicit local marks into risk-engine facts."""

    def snapshot(
        self,
        projection: PaperPortfolioProjection,
        *,
        marks: Mapping[str, float],
    ) -> PortfolioRiskSnapshot:
        instrument_notionals: list[tuple[str, float]] = []
        for position in projection.positions:
            mark = marks.get(position.instrument_id)
            if mark is None or mark <= 0:
                raise ValueError("explicit positive local mark is required for every open local position")
            instrument_notionals.append((position.instrument_id, abs(position.quantity) * mark))
        return PortfolioRiskSnapshot(
            gross_notional=sum(notional for _, notional in instrument_notionals),
            realized_pnl=projection.realized_pnl,
            instrument_notionals=tuple(sorted(instrument_notionals)),
        )
