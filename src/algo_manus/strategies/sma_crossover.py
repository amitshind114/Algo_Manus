"""A simple, transparent moving-average crossover reference strategy."""

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


def _validate_windows(parameters: Mapping[str, int | float]) -> None:
    if parameters["fast_window"] >= parameters["slow_window"]:
        raise ParameterValidationError("fast_window must be smaller than slow_window")


class SmaCrossoverStrategy:
    strategy_id = "sma_crossover"
    metadata = StrategyMetadata(
        strategy_id=strategy_id,
        display_name="SMA crossover",
        version="1.0.0",
        author="Algo Manus",
        description="Long-only moving-average crossover reference strategy.",
        risk_notes="Research reference only; signal output has no order or broker authority.",
        supported_instrument_types=("EQUITY",),
        supported_intervals=("1d",),
        parameter_schema=StrategyParameterSchema(
            definitions=(
                StrategyParameterDefinition(
                    name="fast_window",
                    kind=ParameterKind.INTEGER,
                    default=3,
                    minimum=2,
                    maximum=250,
                    description="Fast simple-moving-average lookback in bars.",
                ),
                StrategyParameterDefinition(
                    name="slow_window",
                    kind=ParameterKind.INTEGER,
                    default=6,
                    minimum=3,
                    maximum=500,
                    description="Slow simple-moving-average lookback in bars.",
                ),
            ),
            cross_field_validator=_validate_windows,
        ),
    )

    def required_history(self, parameters: Mapping[str, float]) -> int:
        fast, slow = self._windows(parameters)
        return slow + 1

    def signal(self, candles: Sequence[Candle], parameters: Mapping[str, float]) -> SignalAction:
        fast, slow = self._windows(parameters)
        if len(candles) < slow + 1:
            return SignalAction.HOLD
        previous = candles[:-1]
        prior_fast = fmean(candle.close for candle in previous[-fast:])
        prior_slow = fmean(candle.close for candle in previous[-slow:])
        current_fast = fmean(candle.close for candle in candles[-fast:])
        current_slow = fmean(candle.close for candle in candles[-slow:])
        if prior_fast <= prior_slow and current_fast > current_slow:
            return SignalAction.ENTER_LONG
        if prior_fast >= prior_slow and current_fast < current_slow:
            return SignalAction.EXIT_LONG
        return SignalAction.HOLD

    @staticmethod
    def _windows(parameters: Mapping[str, float]) -> tuple[int, int]:
        try:
            validated = SmaCrossoverStrategy.metadata.parameter_schema.validate(parameters)
        except ParameterValidationError as exc:
            raise ValueError(f"sma_crossover requires valid fast_window and slow_window: {exc}") from exc
        return int(validated["fast_window"]), int(validated["slow_window"])
