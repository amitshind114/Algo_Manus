"""Durable local risk-policy and kill-switch control contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from algo_manus.domain.risk_engine import CentralRiskPolicy


@dataclass(frozen=True, slots=True)
class KillSwitchChange:
    """One append-only local global kill-switch transition."""

    change_id: str
    active: bool
    reason: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not self.change_id.strip() or not self.reason.strip():
            raise ValueError("kill-switch change ID and reason are required")
        if self.occurred_at.tzinfo is None:
            raise ValueError("kill-switch change timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RiskControlSnapshot:
    """The persisted policy and latest durable kill state used for one decision."""

    policy: CentralRiskPolicy
    policy_persisted_at: datetime
    kill_switch_change: KillSwitchChange

    def __post_init__(self) -> None:
        if self.policy_persisted_at.tzinfo is None:
            raise ValueError("policy persistence timestamp must be timezone-aware")

    @property
    def kill_switch_active(self) -> bool:
        return self.kill_switch_change.active


class RiskControlRepository(Protocol):
    """Persistence boundary for immutable policy versions and control history."""

    def save_policy(self, policy: CentralRiskPolicy, *, persisted_at: datetime) -> None: ...

    def get_policy(self, policy_version: str) -> tuple[CentralRiskPolicy, datetime] | None: ...

    def append_kill_switch_change(self, change: KillSwitchChange) -> None: ...

    def current_kill_switch_change(self) -> KillSwitchChange | None: ...

    def list_kill_switch_changes(self, limit: int = 50) -> tuple[KillSwitchChange, ...]: ...
