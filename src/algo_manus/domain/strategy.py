"""Versioned strategy contracts with explicit parameter revisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Mapping, Protocol, Sequence

from algo_manus.domain.market_data import Candle


class SignalAction(StrEnum):
    HOLD = "HOLD"
    ENTER_LONG = "ENTER_LONG"
    EXIT_LONG = "EXIT_LONG"


@dataclass(frozen=True, slots=True)
class StrategyParameterRevision:
    """Immutable parameters used by exactly one or more named experiments."""

    strategy_id: str
    revision_id: str
    parameters: Mapping[str, float]

    @classmethod
    def create(cls, strategy_id: str, parameters: Mapping[str, float]) -> "StrategyParameterRevision":
        if not strategy_id.strip() or not parameters:
            raise ValueError("strategy_id and at least one parameter are required")
        canonical = json.dumps(dict(parameters), sort_keys=True, separators=(",", ":"))
        return cls(
            strategy_id=strategy_id,
            revision_id=f"PARAM-{sha256((strategy_id + canonical).encode()).hexdigest()[:20]}",
            parameters=dict(parameters),
        )


class Strategy(Protocol):
    """Pure signal generator: it has no provider, database, UI or order access."""

    strategy_id: str

    def required_history(self, parameters: Mapping[str, float]) -> int: ...

    def signal(self, candles: Sequence[Candle], parameters: Mapping[str, float]) -> SignalAction: ...
