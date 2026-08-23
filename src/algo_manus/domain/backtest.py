"""Reproducible backtest specifications, trades and result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json


@dataclass(frozen=True, slots=True)
class BacktestSpec:
    dataset_id: str
    strategy_id: str
    parameter_revision_id: str
    initial_cash: float
    quantity: int
    commission_bps: float
    slippage_bps: float
    force_close_at_end: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_cash", float(self.initial_cash))
        object.__setattr__(self, "quantity", int(self.quantity))
        object.__setattr__(self, "commission_bps", float(self.commission_bps))
        object.__setattr__(self, "slippage_bps", float(self.slippage_bps))
        object.__setattr__(self, "force_close_at_end", bool(self.force_close_at_end))
        if not self.dataset_id or not self.strategy_id or not self.parameter_revision_id:
            raise ValueError("dataset, strategy and parameter revision identifiers are required")
        if self.initial_cash <= 0 or self.quantity <= 0:
            raise ValueError("initial_cash and quantity must be positive")
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("commission_bps and slippage_bps cannot be negative")

    @property
    def spec_id(self) -> str:
        canonical = json.dumps(
            {
                "dataset_id": self.dataset_id,
                "strategy_id": self.strategy_id,
                "parameter_revision_id": self.parameter_revision_id,
                "initial_cash": self.initial_cash,
                "quantity": self.quantity,
                "commission_bps": self.commission_bps,
                "slippage_bps": self.slippage_bps,
                "force_close_at_end": self.force_close_at_end,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"BT-{sha256(canonical.encode()).hexdigest()[:20]}"


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    entry_time: datetime
    exit_time: datetime
    quantity: int
    entry_price: float
    exit_price: float
    gross_pnl: float
    cost: float

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.cost


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    net_pnl: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_rate_pct: float
    profit_factor: float | None
    cagr_pct: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    expectancy: float | None = None
    turnover_pct: float | None = None
    exposure_pct: float | None = None
    average_holding_period_days: float | None = None


@dataclass(frozen=True, slots=True)
class BacktestDrawdownPoint:
    """One immutable point on an equity-derived drawdown curve."""

    timestamp: datetime
    equity: float
    peak_equity: float
    drawdown_pct: float

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("drawdown timestamp must be timezone-aware")
        if self.equity < 0 or self.peak_equity <= 0 or self.drawdown_pct < 0:
            raise ValueError("drawdown point values are invalid")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    spec: BacktestSpec
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[tuple[datetime, float], ...]
    metrics: BacktestMetrics
    drawdown_curve: tuple[BacktestDrawdownPoint, ...] = ()
