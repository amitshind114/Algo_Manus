"""Deterministic bar-based backtester using next-bar fills to avoid look-ahead."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from algo_manus.domain.backtest import (
    BacktestMetrics,
    BacktestResult,
    BacktestSpec,
    BacktestTrade,
)
from algo_manus.domain.market_data import CandleDataset, DataUseCase
from algo_manus.domain.strategy import SignalAction, Strategy, StrategyParameterRevision


@dataclass(frozen=True, slots=True)
class _OpenPosition:
    entry_time: object
    entry_price: float
    quantity: int


class BarBacktestService:
    """Long-only research engine with explicit, conservative execution assumptions.

    A signal derived from candle ``t`` can only be filled at candle ``t + 1``
    open. This engine is intentionally small and auditable; advanced order book,
    intrabar and partial-fill modelling remain later extensions.
    """

    def run(
        self,
        *,
        dataset: CandleDataset,
        strategy: Strategy,
        parameters: StrategyParameterRevision,
        spec: BacktestSpec,
    ) -> BacktestResult:
        if dataset.provenance.use_case is not DataUseCase.RESEARCH:
            raise ValueError("backtests require a research-use dataset")
        if dataset.dataset_id != spec.dataset_id:
            raise ValueError("backtest spec dataset does not match supplied dataset")
        if strategy.strategy_id != spec.strategy_id or parameters.strategy_id != spec.strategy_id:
            raise ValueError("strategy and parameter revision must match backtest spec")
        if parameters.revision_id != spec.parameter_revision_id:
            raise ValueError("parameter revision does not match backtest spec")

        candles = dataset.candles
        if len(candles) <= strategy.required_history(parameters.parameters):
            raise ValueError("dataset has insufficient history for the strategy")

        cash = spec.initial_cash
        position: _OpenPosition | None = None
        trades: list[BacktestTrade] = []
        equity_curve: list[tuple[object, float]] = []

        for index in range(strategy.required_history(parameters.parameters), len(candles) - 1):
            history = candles[: index + 1]
            signal = strategy.signal(history, parameters.parameters)
            next_candle = candles[index + 1]
            if signal is SignalAction.ENTER_LONG and position is None:
                entry_price = self._apply_slippage(next_candle.open, spec.slippage_bps, is_buy=True)
                estimated_cost = self._cost(entry_price, spec.quantity, spec.commission_bps)
                if entry_price * spec.quantity + estimated_cost <= cash:
                    cash -= entry_price * spec.quantity + estimated_cost
                    position = _OpenPosition(next_candle.timestamp, entry_price, spec.quantity)
            elif signal is SignalAction.EXIT_LONG and position is not None:
                trade, cash = self._close(position, next_candle.timestamp, next_candle.open, cash, spec)
                trades.append(trade)
                position = None

            marked_equity = cash + (position.quantity * next_candle.close if position else 0.0)
            equity_curve.append((next_candle.timestamp, marked_equity))

        if position is not None and spec.force_close_at_end:
            final_candle = candles[-1]
            trade, cash = self._close(position, final_candle.timestamp, final_candle.close, cash, spec)
            trades.append(trade)
            equity_curve.append((final_candle.timestamp, cash))

        metrics = self._metrics(spec.initial_cash, cash, trades, equity_curve)
        return BacktestResult(
            spec=spec,
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            metrics=metrics,
        )

    @staticmethod
    def _apply_slippage(price: float, slippage_bps: float, *, is_buy: bool) -> float:
        multiplier = 1 + (slippage_bps / 10_000 if is_buy else -slippage_bps / 10_000)
        return price * multiplier

    def _close(self, position: _OpenPosition, exit_time, raw_exit_price: float, cash: float, spec: BacktestSpec):
        exit_price = self._apply_slippage(raw_exit_price, spec.slippage_bps, is_buy=False)
        gross = (exit_price - position.entry_price) * position.quantity
        cost = self._cost(position.entry_price, position.quantity, spec.commission_bps) + self._cost(
            exit_price, position.quantity, spec.commission_bps
        )
        cash += exit_price * position.quantity - self._cost(exit_price, position.quantity, spec.commission_bps)
        return (
            BacktestTrade(
                entry_time=position.entry_time,
                exit_time=exit_time,
                quantity=position.quantity,
                entry_price=position.entry_price,
                exit_price=exit_price,
                gross_pnl=gross,
                cost=cost,
            ),
            cash,
        )

    @staticmethod
    def _cost(price: float, quantity: int, commission_bps: float) -> float:
        return price * quantity * commission_bps / 10_000

    @staticmethod
    def _metrics(initial_cash: float, final_cash: float, trades: Sequence[BacktestTrade], equity_curve):
        net_pnl = final_cash - initial_cash
        total_return_pct = (net_pnl / initial_cash) * 100
        peak = initial_cash
        max_drawdown = 0.0
        for _, equity in equity_curve:
            peak = max(peak, equity)
            if peak:
                max_drawdown = max(max_drawdown, ((peak - equity) / peak) * 100)
        wins = [trade for trade in trades if trade.net_pnl > 0]
        losses = [trade for trade in trades if trade.net_pnl < 0]
        loss_total = abs(sum(trade.net_pnl for trade in losses))
        profit_factor = sum(trade.net_pnl for trade in wins) / loss_total if loss_total else None
        return BacktestMetrics(
            net_pnl=net_pnl,
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_drawdown,
            trade_count=len(trades),
            win_rate_pct=(len(wins) / len(trades) * 100) if trades else 0.0,
            profit_factor=profit_factor,
        )
