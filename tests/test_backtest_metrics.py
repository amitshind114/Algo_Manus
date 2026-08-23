from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.domain.backtest import BacktestTrade


class BacktestMetricTests(unittest.TestCase):
    def _trade(self, *, entry_day: int, exit_day: int, net_profit: float) -> BacktestTrade:
        start = datetime(2025, 1, 1, 9, 15, tzinfo=timezone.utc)
        return BacktestTrade(
            entry_time=start + timedelta(days=entry_day),
            exit_time=start + timedelta(days=exit_day),
            quantity=10,
            entry_price=100.0,
            exit_price=110.0 if net_profit > 0 else 90.0,
            gross_pnl=net_profit,
            cost=0.0,
        )

    def test_metrics_compute_risk_trade_turnover_and_exposure_context(self) -> None:
        start = datetime(2025, 1, 1, 9, 15, tzinfo=timezone.utc)
        equity = (
            (start, 1_000.0),
            (start + timedelta(days=183), 900.0),
            (start + timedelta(days=366), 1_200.0),
        )
        metrics = BarBacktestService._metrics(
            1_000.0,
            1_200.0,
            (self._trade(entry_day=0, exit_day=10, net_profit=100.0), self._trade(entry_day=20, exit_day=25, net_profit=-50.0)),
            equity,
            exposure_points=2,
            annualization_periods=252,
        )
        curve = BarBacktestService._drawdown_curve(1_000.0, equity)

        self.assertEqual(metrics.net_pnl, 200.0)
        self.assertEqual(metrics.max_drawdown_pct, 10.0)
        self.assertIsNotNone(metrics.cagr_pct)
        self.assertIsNotNone(metrics.sharpe_ratio)
        self.assertIsNotNone(metrics.sortino_ratio)
        self.assertEqual(metrics.expectancy, 25.0)
        self.assertEqual(metrics.turnover_pct, 400.0)
        self.assertEqual(metrics.exposure_pct, 66.66666666666666)
        self.assertEqual(metrics.average_holding_period_days, 7.5)
        self.assertEqual(curve[1].drawdown_pct, 10.0)
        self.assertEqual(curve[-1].peak_equity, 1_200.0)

    def test_insufficient_history_or_trade_context_keeps_metrics_unavailable(self) -> None:
        start = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
        metrics = BarBacktestService._metrics(
            1_000.0,
            1_000.0,
            (),
            ((start, 1_000.0),),
            exposure_points=0,
            annualization_periods=252,
        )
        intraday_metrics = BarBacktestService._metrics(
            1_000.0,
            1_010.0,
            (),
            ((start, 1_000.0), (start + timedelta(days=1), 1_010.0)),
            exposure_points=0,
            annualization_periods=None,
        )

        self.assertIsNone(metrics.cagr_pct)
        self.assertIsNone(metrics.sharpe_ratio)
        self.assertIsNone(metrics.sortino_ratio)
        self.assertIsNone(metrics.expectancy)
        self.assertEqual(metrics.turnover_pct, 0.0)
        self.assertEqual(metrics.exposure_pct, 0.0)
        self.assertIsNone(metrics.average_holding_period_days)
        self.assertIsNone(intraday_metrics.sharpe_ratio)
        self.assertIsNone(intraday_metrics.sortino_ratio)


if __name__ == "__main__":
    unittest.main()
