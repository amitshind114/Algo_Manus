"""Built-in pure strategy implementations."""

from .registry import (
    StrategyCompatibilityError,
    StrategyNotRegisteredError,
    StrategyRegistry,
    built_in_registry,
)
from .sma_crossover import SmaCrossoverStrategy

__all__ = [
    "SmaCrossoverStrategy",
    "StrategyCompatibilityError",
    "StrategyNotRegisteredError",
    "StrategyRegistry",
    "built_in_registry",
]
