"""A simple, transparent moving-average crossover reference strategy."""

from __future__ import annotations

from statistics import fmean
from typing import Mapping, Sequence

from algo_manus.domain.market_data import Candle
from algo_manus.domain.strategy import SignalAction


class SmaCrossoverStrategy:
    strategy_id = "sma_crossover"

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
            fast = int(parameters["fast_window"])
            slow = int(parameters["slow_window"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("sma_crossover requires integer fast_window and slow_window") from exc
        if fast <= 0 or slow <= 0 or fast >= slow:
            raise ValueError("fast_window must be positive and smaller than slow_window")
        return fast, slow
