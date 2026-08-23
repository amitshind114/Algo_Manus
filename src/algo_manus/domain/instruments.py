"""Canonical India-market instrument and immutable master-snapshot contracts.

These contracts intentionally contain no SDK, database, UI, network or execution
logic. Broker-specific adapters translate their master records into this model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
from hashlib import sha256
from typing import Mapping


class InstrumentType(StrEnum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    COMMODITY = "COMMODITY"


class InstrumentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"
    UNRESOLVED = "UNRESOLVED"


class OptionType(StrEnum):
    CALL = "CE"
    PUT = "PE"


@dataclass(frozen=True, slots=True)
class Instrument:
    """A broker-resolved tradable or reference instrument.

    ``instrument_id`` is derived from broker, exchange, segment and broker token.
    A display name is not an identity: names and trading symbols can change.
    """

    broker: str
    exchange: str
    segment: str
    broker_token: str
    trading_symbol: str
    display_name: str
    instrument_type: InstrumentType
    status: InstrumentStatus = InstrumentStatus.ACTIVE
    expiry: date | None = None
    strike: float | None = None
    option_type: OptionType | None = None
    lot_size: int | None = None
    tick_size: float | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "broker": self.broker,
            "exchange": self.exchange,
            "segment": self.segment,
            "broker_token": self.broker_token,
            "trading_symbol": self.trading_symbol,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"Instrument requires non-empty fields: {', '.join(missing)}")
        if self.instrument_type is InstrumentType.OPTION:
            if self.expiry is None or self.strike is None or self.option_type is None:
                raise ValueError("Option instrument requires expiry, strike and option_type")
        if self.lot_size is not None and self.lot_size <= 0:
            raise ValueError("lot_size must be positive when supplied")
        if self.tick_size is not None and self.tick_size <= 0:
            raise ValueError("tick_size must be positive when supplied")

    @property
    def instrument_id(self) -> str:
        return ":".join(
            part.strip().upper()
            for part in (self.broker, self.exchange, self.segment, self.broker_token)
        )


@dataclass(frozen=True, slots=True)
class InstrumentMasterSnapshot:
    """An immutable broker-master snapshot used for reproducible universes."""

    snapshot_id: str
    broker: str
    downloaded_at: datetime
    source_uri: str
    content_sha256: str
    instruments: tuple[Instrument, ...]

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip() or not self.broker.strip():
            raise ValueError("snapshot_id and broker are required")
        if len(self.content_sha256) != 64:
            raise ValueError("content_sha256 must be a SHA-256 hex digest")
        if self.downloaded_at.tzinfo is None:
            raise ValueError("downloaded_at must be timezone-aware")
        identities = [instrument.instrument_id for instrument in self.instruments]
        duplicates = sorted({identity for identity in identities if identities.count(identity) > 1})
        if duplicates:
            raise ValueError(f"duplicate instrument identities in snapshot: {duplicates}")
        brokers = {instrument.broker.upper() for instrument in self.instruments}
        if brokers and brokers != {self.broker.upper()}:
            raise ValueError("all instruments must belong to snapshot broker")

    @property
    def active_instruments(self) -> tuple[Instrument, ...]:
        return tuple(
            instrument
            for instrument in self.instruments
            if instrument.status is InstrumentStatus.ACTIVE
        )

    @classmethod
    def create(
        cls,
        *,
        broker: str,
        source_uri: str,
        raw_content: bytes,
        instruments: tuple[Instrument, ...],
        downloaded_at: datetime | None = None,
    ) -> "InstrumentMasterSnapshot":
        timestamp = downloaded_at or datetime.now(timezone.utc)
        digest = sha256(raw_content).hexdigest()
        snapshot_id = f"{broker.upper()}-{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{digest[:12]}"
        return cls(
            snapshot_id=snapshot_id,
            broker=broker,
            downloaded_at=timestamp,
            source_uri=source_uri,
            content_sha256=digest,
            instruments=instruments,
        )
