"""Explicit registry for pure local strategy implementations."""

from __future__ import annotations

from typing import Iterable, Mapping

from algo_manus.domain.strategy import Strategy, StrategyMetadata


class StrategyNotRegisteredError(KeyError):
    """Raised when a requested stable strategy ID is not in this registry."""


class StrategyCompatibilityError(ValueError):
    """Raised when a strategy is asked to run outside its declared support."""


class StrategyRegistry:
    """In-memory registry with explicit registration and no plugin side effects."""

    def __init__(self, strategies: Iterable[Strategy] = ()) -> None:
        self._strategies: dict[str, Strategy] = {}
        for strategy in strategies:
            self.register(strategy)

    def register(self, strategy: Strategy) -> None:
        metadata = strategy.metadata
        if strategy.strategy_id != metadata.strategy_id:
            raise ValueError("strategy ID must match its metadata ID")
        if strategy.strategy_id in self._strategies:
            raise ValueError(f"strategy already registered: {strategy.strategy_id}")
        self._strategies[strategy.strategy_id] = strategy

    def get(self, strategy_id: str) -> Strategy:
        try:
            return self._strategies[strategy_id]
        except KeyError as exc:
            raise StrategyNotRegisteredError(f"strategy is not registered: {strategy_id}") from exc

    def metadata(self) -> tuple[StrategyMetadata, ...]:
        return tuple(
            self._strategies[strategy_id].metadata
            for strategy_id in sorted(self._strategies)
        )

    def validate_parameters(
        self, strategy_id: str, parameters: Mapping[str, object]
    ) -> Mapping[str, int | float]:
        return self.get(strategy_id).metadata.parameter_schema.validate(parameters)

    def validate_compatibility(
        self, strategy_id: str, *, instrument_type: str, interval: str
    ) -> None:
        metadata = self.get(strategy_id).metadata
        if instrument_type not in metadata.supported_instrument_types:
            raise StrategyCompatibilityError(
                f"{strategy_id} does not support instrument type {instrument_type}"
            )
        if interval not in metadata.supported_intervals:
            raise StrategyCompatibilityError(
                f"{strategy_id} does not support interval {interval}"
            )


def built_in_strategies() -> tuple[Strategy, ...]:
    """Return explicit built-ins; no filesystem/module scanning is performed."""

    from algo_manus.strategies.high_value import (
        BollingerBreakoutStrategy,
        EmaCrossoverStrategy,
        MacdSignalStrategy,
        RsiMeanReversionStrategy,
        TripleEmaCrossoverStrategy,
    )
    from algo_manus.strategies.rsi_threshold_reversion import RsiThresholdReversionStrategy
    from algo_manus.strategies.sma_crossover import SmaCrossoverStrategy

    return (
        BollingerBreakoutStrategy(),
        EmaCrossoverStrategy(),
        MacdSignalStrategy(),
        RsiMeanReversionStrategy(),
        RsiThresholdReversionStrategy(),
        SmaCrossoverStrategy(),
        TripleEmaCrossoverStrategy(),
    )


def built_in_registry() -> StrategyRegistry:
    """Build the deterministic registry used by local research entry points."""

    return StrategyRegistry(built_in_strategies())
