"""Conservative local RSI threshold-reversion research strategy.

The strategy consumes only supplied historical candles. It emits a long-only
research signal; it cannot access data providers, accounts, brokers, paper
orders, or live execution services.
"""

from __future__ import annotations

from statistics import fmean
from typing import Mapping, Sequence

from algo_manus.domain.market_data import Candle
from algo_manus.domain.strategy import (
    ParameterKind,
    ParameterValidationError,
    SignalAction,
    StrategyMetadata,
    StrategyParameterDefinition,
    StrategyParameterSchema,
)


def _validate_thresholds(parameters: Mapping[str, int | float]) -> None:
    if parameters["entry_threshold"] >= parameters["exit_threshold"]:
        raise ParameterValidationError("entry_threshold must be smaller than exit_threshold")


def _rsi(closes: Sequence[float], window: int) -> float:
    changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    if len(changes) < window:
        raise ValueError("RSI requires at least one complete window")
    gains = [max(change, 0.0) for change in changes[-window:]]
    losses = [max(-change, 0.0) for change in changes[-window:]]
    average_gain = fmean(gains)
    average_loss = fmean(losses)
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + (average_gain / average_loss)))


class RsiThresholdReversionStrategy:
    """Long-only local mean-reversion research signal using threshold crossings."""

    strategy_id = "rsi_threshold_reversion"
    metadata = StrategyMetadata(
        strategy_id=strategy_id,
        display_name="RSI threshold reversion",
        version="1.0.0",
        author="Algo Manus",
        description="Long-only RSI threshold-crossing mean-reversion research strategy.",
        risk_notes=(
            "Research reference only. Signals use closed local bars and have no broker, paper-order or live-execution authority."
        ),
        supported_instrument_types=("EQUITY",),
        supported_intervals=("1d",),
        parameter_schema=StrategyParameterSchema(
            definitions=(
                StrategyParameterDefinition("rsi_window", ParameterKind.INTEGER, 5, "RSI lookback.", 2, 250),
                StrategyParameterDefinition(
                    "entry_threshold", ParameterKind.NUMBER, 30.0, "Enter after RSI crosses below this threshold.", 0.0, 100.0
                ),
                StrategyParameterDefinition(
                    "exit_threshold", ParameterKind.NUMBER, 70.0, "Exit after RSI crosses above this threshold.", 0.0, 100.0
                ),
            ),
            cross_field_validator=_validate_thresholds,
        ),
    )

    def required_history(self, parameters: Mapping[str, float]) -> int:
        return int(self.metadata.parameter_schema.validate(parameters)["rsi_window"]) + 1

    def signal(self, candles: Sequence[Candle], parameters: Mapping[str, float]) -> SignalAction:
        values = self.metadata.parameter_schema.validate(parameters)
        window = int(values["rsi_window"])
        if len(candles) < window + 2:
            return SignalAction.HOLD
        closes = [candle.close for candle in candles]
        previous_rsi = _rsi(closes[:-1], window)
        current_rsi = _rsi(closes, window)
        entry_threshold = float(values["entry_threshold"])
        exit_threshold = float(values["exit_threshold"])
        if previous_rsi >= entry_threshold and current_rsi < entry_threshold:
            return SignalAction.ENTER_LONG
        if previous_rsi <= exit_threshold and current_rsi > exit_threshold:
            return SignalAction.EXIT_LONG
        return SignalAction.HOLD
