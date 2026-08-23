"""Operational mode and health contracts for the local-first platform."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Mapping


class RuntimeMode(StrEnum):
    RESEARCH = "RESEARCH"
    PAPER = "PAPER"


class HealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    component: str
    status: HealthStatus
    detail: str


@dataclass(frozen=True, slots=True)
class LocalHealthSnapshot:
    observed_at: datetime
    mode: RuntimeMode
    components: tuple[ComponentHealth, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("health snapshot time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AuditRecord:
    event_id: str
    occurred_at: datetime
    category: str
    action: str
    correlation_id: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("audit event time must be timezone-aware")
        if not self.category or not self.action or not self.correlation_id:
            raise ValueError("audit category, action and correlation ID are required")
