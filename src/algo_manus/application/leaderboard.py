"""Core-engine KPI leaderboard projection for comparable experiment batches."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from algo_manus.domain.experiment import ExperimentBatch
from algo_manus.domain.backtest import BacktestOutcome


class LeaderboardSort(StrEnum):
    NET_PNL = "NET_PNL"
    TOTAL_RETURN = "TOTAL_RETURN"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    PROFIT_FACTOR = "PROFIT_FACTOR"
    WIN_RATE = "WIN_RATE"


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    instrument_id: str
    dataset_id: str
    result_spec_id: str
    net_pnl: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_rate_pct: float
    profit_factor: float | None
    data_quality_note: str
    outcome: BacktestOutcome | None


class LeaderboardService:
    """Produces a display-ready projection without labelling any row 'best'."""

    def rows(self, batch: ExperimentBatch, sort_by: LeaderboardSort) -> tuple[LeaderboardRow, ...]:
        rows = tuple(
            LeaderboardRow(
                instrument_id=item.instrument_id,
                dataset_id=item.dataset_id,
                result_spec_id=item.backtest.spec.spec_id,
                net_pnl=item.backtest.metrics.net_pnl,
                total_return_pct=item.backtest.metrics.total_return_pct,
                max_drawdown_pct=item.backtest.metrics.max_drawdown_pct,
                trade_count=item.backtest.metrics.trade_count,
                win_rate_pct=item.backtest.metrics.win_rate_pct,
                profit_factor=item.backtest.metrics.profit_factor,
                data_quality_note=item.data_quality_note,
                outcome=item.backtest.outcome,
            )
            for item in batch.results
        )
        reverse = sort_by is not LeaderboardSort.MAX_DRAWDOWN
        return tuple(sorted(rows, key=lambda row: self._key(row, sort_by), reverse=reverse))

    @staticmethod
    def _key(row: LeaderboardRow, sort_by: LeaderboardSort) -> float:
        if sort_by is LeaderboardSort.NET_PNL:
            return row.net_pnl
        if sort_by is LeaderboardSort.TOTAL_RETURN:
            return row.total_return_pct
        if sort_by is LeaderboardSort.MAX_DRAWDOWN:
            return row.max_drawdown_pct
        if sort_by is LeaderboardSort.PROFIT_FACTOR:
            return row.profit_factor if row.profit_factor is not None else -1.0
        return row.win_rate_pct
