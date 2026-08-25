"""Selected pure local strategy adaptations inspired by Eagle Base ideas.

These strategies only consume typed local candles and validated parameters. They do
not access providers, databases, UI state, credentials, accounts or orders.
"""

from __future__ import annotations

from math import sqrt
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


def _windows(parameters: Mapping[str, int | float], strategy_id: str, names: tuple[str, ...]) -> tuple[int, ...]:
    try:
        values = StrategyParameterSchema(
            definitions=tuple(
                StrategyParameterDefinition(name=name, kind=ParameterKind.INTEGER, default=2, minimum=2, maximum=500, description=name)
                for name in names
            )
        ).validate(parameters)
    except ParameterValidationError as exc:
        raise ValueError(f"{strategy_id} requires valid integer windows: {exc}") from exc
    return tuple(int(values[name]) for name in names)


def _ema(values: Sequence[float], window: int) -> float:
    if len(values) < window:
        raise ValueError("EMA requires at least one complete window")
    result = fmean(values[:window])
    alpha = 2.0 / (window + 1)
    for value in values[window:]:
        result = (value * alpha) + (result * (1.0 - alpha))
    return result


def _ema_series(values: Sequence[float], window: int) -> tuple[float, ...]:
    if len(values) < window:
        return ()
    result = fmean(values[:window])
    output = [result]
    alpha = 2.0 / (window + 1)
    for value in values[window:]:
        result = (value * alpha) + (result * (1.0 - alpha))
        output.append(result)
    return tuple(output)


def _rsi(values: Sequence[float], window: int) -> float:
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    if len(changes) < window:
        raise ValueError("RSI requires at least one complete window")
    gains = [max(change, 0.0) for change in changes[-window:]]
    losses = [max(-change, 0.0) for change in changes[-window:]]
    average_gain = fmean(gains)
    average_loss = fmean(losses)
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + (average_gain / average_loss)))


def _validate_two_windows(parameters: Mapping[str, int | float]) -> None:
    if parameters["fast_window"] >= parameters["slow_window"]:
        raise ParameterValidationError("fast_window must be smaller than slow_window")


def _validate_three_windows(parameters: Mapping[str, int | float]) -> None:
    if not (parameters["fast_window"] < parameters["middle_window"] < parameters["slow_window"]):
        raise ParameterValidationError("windows must be ordered fast < middle < slow")


def _validate_rsi_levels(parameters: Mapping[str, int | float]) -> None:
    if parameters["oversold"] >= parameters["overbought"]:
        raise ParameterValidationError("oversold must be smaller than overbought")


class EmaCrossoverStrategy:
    strategy_id = "ema_crossover"
    metadata = StrategyMetadata(
        strategy_id=strategy_id,
        display_name="EMA crossover",
        version="1.0.0",
        author="Algo Manus",
        description="Long-only exponential-moving-average crossover research strategy.",
        risk_notes="Research reference only; signal output has no order or broker authority.",
        supported_instrument_types=("EQUITY",),
        supported_intervals=("1d",),
        parameter_schema=StrategyParameterSchema(
            definitions=(
                StrategyParameterDefinition("fast_window", ParameterKind.INTEGER, 3, "Fast EMA lookback.", 2, 250),
                StrategyParameterDefinition("slow_window", ParameterKind.INTEGER, 6, "Slow EMA lookback.", 3, 500),
            ),
            cross_field_validator=_validate_two_windows,
        ),
    )

    def required_history(self, parameters: Mapping[str, float]) -> int:
        return int(self.metadata.parameter_schema.validate(parameters)["slow_window"]) + 1

    def signal(self, candles: Sequence[Candle], parameters: Mapping[str, float]) -> SignalAction:
        fast, slow = _windows(parameters, self.strategy_id, ("fast_window", "slow_window"))
        if len(candles) < slow + 1:
            return SignalAction.HOLD
        previous = [c.close for c in candles[:-1]]
        current = [c.close for c in candles]
        prior_fast, prior_slow = _ema(previous, fast), _ema(previous, slow)
        current_fast, current_slow = _ema(current, fast), _ema(current, slow)
        if prior_fast <= prior_slow and current_fast > current_slow:
            return SignalAction.ENTER_LONG
        if prior_fast >= prior_slow and current_fast < current_slow:
            return SignalAction.EXIT_LONG
        return SignalAction.HOLD


class RsiMeanReversionStrategy:
    strategy_id = "rsi_mean_reversion"
    metadata = StrategyMetadata(
        strategy_id=strategy_id,
        display_name="RSI mean reversion",
        version="1.0.0",
        author="Algo Manus",
        description="Long-only RSI oversold/overbought research strategy.",
        risk_notes="Research reference only; thresholds are not investment advice.",
        supported_instrument_types=("EQUITY",),
        supported_intervals=("1d",),
        parameter_schema=StrategyParameterSchema(
            definitions=(
                StrategyParameterDefinition("rsi_window", ParameterKind.INTEGER, 5, "RSI lookback.", 2, 250),
                StrategyParameterDefinition("oversold", ParameterKind.NUMBER, 30.0, "Oversold threshold.", 0.0, 100.0),
                StrategyParameterDefinition("overbought", ParameterKind.NUMBER, 70.0, "Overbought threshold.", 0.0, 100.0),
            ),
            cross_field_validator=_validate_rsi_levels,
        ),
    )

    def required_history(self, parameters: Mapping[str, float]) -> int:
        return int(self.metadata.parameter_schema.validate(parameters)["rsi_window"]) + 1

    def signal(self, candles: Sequence[Candle], parameters: Mapping[str, float]) -> SignalAction:
        validated = self.metadata.parameter_schema.validate(parameters)
        window = int(validated["rsi_window"])
        if len(candles) < window + 1:
            return SignalAction.HOLD
        value = _rsi([c.close for c in candles], window)
        if value <= float(validated["oversold"]):
            return SignalAction.ENTER_LONG
        if value >= float(validated["overbought"]):
            return SignalAction.EXIT_LONG
        return SignalAction.HOLD


class MacdSignalStrategy:
    strategy_id = "macd_signal"
    metadata = StrategyMetadata(
        strategy_id=strategy_id,
        display_name="MACD signal",
        version="1.0.0",
        author="Algo Manus",
        description="Long-only MACD and signal-line crossover research strategy.",
        risk_notes="Research reference only; indicator output has no execution authority.",
        supported_instrument_types=("EQUITY",),
        supported_intervals=("1d",),
        parameter_schema=StrategyParameterSchema(
            definitions=(
                StrategyParameterDefinition("fast_window", ParameterKind.INTEGER, 3, "MACD fast EMA.", 2, 100),
                StrategyParameterDefinition("slow_window", ParameterKind.INTEGER, 6, "MACD slow EMA.", 3, 250),
                StrategyParameterDefinition("signal_window", ParameterKind.INTEGER, 2, "MACD signal EMA.", 2, 100),
            ),
            cross_field_validator=_validate_two_windows,
        ),
    )

    def required_history(self, parameters: Mapping[str, float]) -> int:
        values = self.metadata.parameter_schema.validate(parameters)
        return int(values["slow_window"]) + int(values["signal_window"]) + 1

    def signal(self, candles: Sequence[Candle], parameters: Mapping[str, float]) -> SignalAction:
        values = self.metadata.parameter_schema.validate(parameters)
        fast, slow, signal_window = (int(values[name]) for name in ("fast_window", "slow_window", "signal_window"))
        closes = [c.close for c in candles]
        if len(closes) < slow + signal_window + 1:
            return SignalAction.HOLD
        macd_series = tuple(
            _ema(closes[:index], fast) - _ema(closes[:index], slow)
            for index in range(slow, len(closes) + 1)
        )
        if len(macd_series) < signal_window + 1:
            return SignalAction.HOLD
        signal_previous = _ema(macd_series[:-1], signal_window)
        signal_current = _ema(macd_series, signal_window)
        if macd_series[-2] <= signal_previous and macd_series[-1] > signal_current:
            return SignalAction.ENTER_LONG
        if macd_series[-2] >= signal_previous and macd_series[-1] < signal_current:
            return SignalAction.EXIT_LONG
        return SignalAction.HOLD


class BollingerBreakoutStrategy:
    strategy_id = "bollinger_breakout"
    metadata = StrategyMetadata(
        strategy_id=strategy_id,
        display_name="Bollinger breakout",
        version="1.0.0",
        author="Algo Manus",
        description="Long-only close breakout from a rolling Bollinger band.",
        risk_notes="Research reference only; band breaks are not recommendations.",
        supported_instrument_types=("EQUITY",),
        supported_intervals=("1d",),
        parameter_schema=StrategyParameterSchema(
            definitions=(
                StrategyParameterDefinition("window", ParameterKind.INTEGER, 5, "Bollinger lookback.", 2, 250),
                StrategyParameterDefinition("deviation", ParameterKind.NUMBER, 2.0, "Standard-deviation multiplier.", 0.1, 10.0),
            )
        ),
    )

    def required_history(self, parameters: Mapping[str, float]) -> int:
        return int(self.metadata.parameter_schema.validate(parameters)["window"]) + 1

    def signal(self, candles: Sequence[Candle], parameters: Mapping[str, float]) -> SignalAction:
        values = self.metadata.parameter_schema.validate(parameters)
        window, deviation = int(values["window"]), float(values["deviation"])
        if len(candles) < window + 1:
            return SignalAction.HOLD
        closes = [c.close for c in candles[-window:]]
        mean = fmean(closes)
        standard_deviation = sqrt(fmean([(value - mean) ** 2 for value in closes]))
        close = closes[-1]
        if close > mean + (deviation * standard_deviation):
            return SignalAction.ENTER_LONG
        if close < mean - (deviation * standard_deviation):
            return SignalAction.EXIT_LONG
        return SignalAction.HOLD


class TripleEmaCrossoverStrategy:
    strategy_id = "triple_ema_crossover"
    metadata = StrategyMetadata(
        strategy_id=strategy_id,
        display_name="Triple EMA crossover",
        version="1.0.0",
        author="Algo Manus",
        description="Long-only ordered three-EMA trend research strategy.",
        risk_notes="Research reference only; trend state has no order authority.",
        supported_instrument_types=("EQUITY",),
        supported_intervals=("1d",),
        parameter_schema=StrategyParameterSchema(
            definitions=(
                StrategyParameterDefinition("fast_window", ParameterKind.INTEGER, 3, "Fast EMA.", 2, 100),
                StrategyParameterDefinition("middle_window", ParameterKind.INTEGER, 5, "Middle EMA.", 3, 200),
                StrategyParameterDefinition("slow_window", ParameterKind.INTEGER, 8, "Slow EMA.", 4, 500),
            ),
            cross_field_validator=_validate_three_windows,
        ),
    )

    def required_history(self, parameters: Mapping[str, float]) -> int:
        return int(self.metadata.parameter_schema.validate(parameters)["slow_window"]) + 1

    def signal(self, candles: Sequence[Candle], parameters: Mapping[str, float]) -> SignalAction:
        values = self.metadata.parameter_schema.validate(parameters)
        fast, middle, slow = (int(values[name]) for name in ("fast_window", "middle_window", "slow_window"))
        if len(candles) < slow + 1:
            return SignalAction.HOLD
        closes = [c.close for c in candles]
        previous = closes[:-1]
        prior = (_ema(previous, fast), _ema(previous, middle), _ema(previous, slow))
        current = (_ema(closes, fast), _ema(closes, middle), _ema(closes, slow))
        if not (prior[0] > prior[1] > prior[2]) and current[0] > current[1] > current[2]:
            return SignalAction.ENTER_LONG
        if not (prior[0] < prior[1] < prior[2]) and current[0] < current[1] < current[2]:
            return SignalAction.EXIT_LONG
        return SignalAction.HOLD
