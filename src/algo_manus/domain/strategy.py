"""Pure, versioned strategy contracts with validated metadata and parameters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from typing import Callable, Mapping, Protocol, Sequence

from algo_manus.domain.market_data import Candle


class SignalAction(StrEnum):
    HOLD = "HOLD"
    ENTER_LONG = "ENTER_LONG"
    EXIT_LONG = "EXIT_LONG"


class ParameterKind(StrEnum):
    """Supported parameter representations for a registered strategy."""

    INTEGER = "integer"
    NUMBER = "number"


class ParameterValidationError(ValueError):
    """Raised when a submitted strategy configuration violates its schema."""


@dataclass(frozen=True, slots=True)
class StrategyParameterDefinition:
    """One declarative strategy parameter used by API and UI validation alike."""

    name: str
    kind: ParameterKind
    default: int | float
    description: str
    minimum: int | float | None = None
    maximum: int | float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("strategy parameter name is required")
        if not self.description.strip():
            raise ValueError("strategy parameter description is required")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("strategy parameter minimum cannot exceed maximum")
        self._validate_scalar(self.default)

    def _validate_scalar(self, value: object) -> int | float:
        if isinstance(value, bool):
            raise ParameterValidationError(f"{self.name} must be a {self.kind.value}")
        if self.kind is ParameterKind.INTEGER:
            if not isinstance(value, int):
                raise ParameterValidationError(f"{self.name} must be an integer")
        elif not isinstance(value, (int, float)):
            raise ParameterValidationError(f"{self.name} must be a number")
        normalized = int(value) if self.kind is ParameterKind.INTEGER else float(value)
        if self.minimum is not None and normalized < self.minimum:
            raise ParameterValidationError(f"{self.name} must be at least {self.minimum}")
        if self.maximum is not None and normalized > self.maximum:
            raise ParameterValidationError(f"{self.name} must be at most {self.maximum}")
        return normalized

    def validate(self, value: object) -> int | float:
        """Normalize and validate one untrusted parameter value."""

        return self._validate_scalar(value)


CrossFieldValidator = Callable[[Mapping[str, int | float]], None]


@dataclass(frozen=True, slots=True)
class StrategyParameterSchema:
    """Strict schema that gives every strategy one shared validation boundary."""

    definitions: tuple[StrategyParameterDefinition, ...]
    cross_field_validator: CrossFieldValidator | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        names = [item.name for item in self.definitions]
        if not names:
            raise ValueError("strategy parameter schema requires at least one definition")
        if len(names) != len(set(names)):
            raise ValueError("strategy parameter schema contains duplicate names")

    def defaults(self) -> Mapping[str, int | float]:
        return {definition.name: definition.default for definition in self.definitions}

    def validate(self, parameters: Mapping[str, object]) -> Mapping[str, int | float]:
        expected = {definition.name for definition in self.definitions}
        supplied = set(parameters)
        missing = expected - supplied
        unknown = supplied - expected
        if missing:
            raise ParameterValidationError(f"missing strategy parameters: {', '.join(sorted(missing))}")
        if unknown:
            raise ParameterValidationError(f"unknown strategy parameters: {', '.join(sorted(unknown))}")
        normalized = {
            definition.name: definition.validate(parameters[definition.name])
            for definition in self.definitions
        }
        if self.cross_field_validator is not None:
            self.cross_field_validator(normalized)
        return normalized


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    """Stable, display-safe facts for one registered strategy version."""

    strategy_id: str
    display_name: str
    version: str
    author: str
    description: str
    risk_notes: str
    supported_instrument_types: tuple[str, ...]
    supported_intervals: tuple[str, ...]
    parameter_schema: StrategyParameterSchema

    def __post_init__(self) -> None:
        required_text = {
            "strategy_id": self.strategy_id,
            "display_name": self.display_name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "risk_notes": self.risk_notes,
        }
        if any(not value.strip() for value in required_text.values()):
            raise ValueError("strategy metadata text fields are required")
        if not self.supported_instrument_types or not self.supported_intervals:
            raise ValueError("strategy metadata needs supported instruments and intervals")


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """Read-only context reserved for future strategy evaluation contracts."""

    instrument_id: str
    instrument_type: str
    interval: str
    candles: Sequence[Candle]
    portfolio_state: Mapping[str, int | float]
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.instrument_id.strip() or not self.instrument_type.strip() or not self.interval.strip():
            raise ValueError("strategy context needs instrument identity, type and interval")
        if self.as_of.tzinfo is None:
            raise ValueError("strategy context timestamp must be timezone-aware")


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
    metadata: StrategyMetadata

    def required_history(self, parameters: Mapping[str, float]) -> int: ...

    def signal(self, candles: Sequence[Candle], parameters: Mapping[str, float]) -> SignalAction: ...
