"""Small, dependency-free local configuration for the Phase 1 foundation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LocalSettings:
    data_dir: Path
    instrument_max_age_hours: int
    default_broker: str
    live_trading_enabled: bool

    @classmethod
    def from_environment(cls) -> "LocalSettings":
        max_age = int(os.environ.get("ALGO_MANUS_INSTRUMENT_MAX_AGE_HOURS", "24"))
        if max_age <= 0:
            raise ValueError("ALGO_MANUS_INSTRUMENT_MAX_AGE_HOURS must be positive")
        live_enabled = os.environ.get("ALGO_MANUS_LIVE_TRADING", "false").lower() == "true"
        if live_enabled:
            raise ValueError("live trading is not available in Phase 1")
        return cls(
            data_dir=Path(os.environ.get("ALGO_MANUS_DATA_DIR", ".local/algo_manus")),
            instrument_max_age_hours=max_age,
            default_broker=os.environ.get("ALGO_MANUS_DEFAULT_BROKER", "angel_one"),
            live_trading_enabled=False,
        )
