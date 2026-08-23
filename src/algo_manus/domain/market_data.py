"""Canonical source-aware market-data contracts for research and paper workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json


class DataSourceKind(StrEnum):
    BROKER = "BROKER"
    FIXTURE = "FIXTURE"
    PUBLIC_FALLBACK = "PUBLIC_FALLBACK"


class DataUseCase(StrEnum):
    RESEARCH = "RESEARCH"
    PAPER = "PAPER"
    RISK = "RISK"


@dataclass(frozen=True, slots=True)
class Candle:
    """One closed OHLCV bar with an explicit exchange timestamp."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("candle timestamp must be timezone-aware")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC values must be positive")
        if self.high < max(self.open, self.low, self.close):
            raise ValueError("high must be at least open, low and close")
        if self.low > min(self.open, self.high, self.close):
            raise ValueError("low must be at most open, high and close")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")


@dataclass(frozen=True, slots=True)
class DataProvenance:
    """Origin and policy context retained with every accepted candle dataset."""

    source_name: str
    source_kind: DataSourceKind
    source_uri: str
    retrieved_at: datetime
    raw_content_sha256: str
    adjustment_basis: str
    use_case: DataUseCase

    def __post_init__(self) -> None:
        if not self.source_name.strip() or not self.source_uri.strip():
            raise ValueError("source_name and source_uri are required")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if len(self.raw_content_sha256) != 64:
            raise ValueError("raw_content_sha256 must be a SHA-256 hex digest")
        if not self.adjustment_basis.strip():
            raise ValueError("adjustment_basis is required")


@dataclass(frozen=True, slots=True)
class CandleDataset:
    """Immutable candles plus provenance pinned to one instrument and interval."""

    dataset_id: str
    instrument_id: str
    interval: str
    provenance: DataProvenance
    candles: tuple[Candle, ...]

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.instrument_id.strip() or not self.interval.strip():
            raise ValueError("dataset_id, instrument_id and interval are required")
        if not self.candles:
            raise ValueError("a candle dataset requires at least one candle")
        timestamps = [candle.timestamp for candle in self.candles]
        if timestamps != sorted(timestamps) or len(set(timestamps)) != len(timestamps):
            raise ValueError("candles must be strictly ordered with unique timestamps")

    @classmethod
    def create(
        cls,
        *,
        instrument_id: str,
        interval: str,
        provenance: DataProvenance,
        candles: tuple[Candle, ...],
    ) -> "CandleDataset":
        canonical = {
            "instrument_id": instrument_id,
            "interval": interval,
            "provenance_hash": provenance.raw_content_sha256,
            "candles": [
                {
                    "timestamp": candle.timestamp.astimezone(timezone.utc).isoformat(),
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                }
                for candle in candles
            ],
        }
        digest = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return cls(
            dataset_id=f"DATA-{digest[:20]}",
            instrument_id=instrument_id,
            interval=interval,
            provenance=provenance,
            candles=candles,
        )
