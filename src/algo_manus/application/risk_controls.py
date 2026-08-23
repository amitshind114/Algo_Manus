"""Local read/write use cases for persisted central-risk controls."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from algo_manus.domain.risk_controls import (
    KillSwitchChange,
    RiskControlRepository,
    RiskControlSnapshot,
)
from algo_manus.domain.risk_engine import CentralRiskPolicy


class LocalRiskControlService:
    """Creates and loads explicit local control evidence without gateway authority."""

    def __init__(self, repository: RiskControlRepository) -> None:
        self._repository = repository

    def save_policy(self, policy: CentralRiskPolicy, *, now: datetime | None = None) -> None:
        occurred_at = now or datetime.now(timezone.utc)
        self._repository.save_policy(policy, persisted_at=occurred_at)

    def set_kill_switch(
        self,
        *,
        active: bool,
        reason: str,
        now: datetime | None = None,
    ) -> KillSwitchChange:
        occurred_at = now or datetime.now(timezone.utc)
        canonical = f"{active}|{reason}|{occurred_at.isoformat()}"
        change = KillSwitchChange(
            change_id=f"KILL-{sha256(canonical.encode()).hexdigest()[:20]}",
            active=active,
            reason=reason,
            occurred_at=occurred_at,
        )
        self._repository.append_kill_switch_change(change)
        return change

    def snapshot(self, policy_version: str) -> RiskControlSnapshot:
        policy_record = self._repository.get_policy(policy_version)
        if policy_record is None:
            raise ValueError("requested central risk policy is not persisted locally")
        kill_change = self._repository.current_kill_switch_change()
        if kill_change is None:
            raise ValueError("durable kill-switch state is not initialized")
        policy, persisted_at = policy_record
        return RiskControlSnapshot(
            policy=policy,
            policy_persisted_at=persisted_at,
            kill_switch_change=kill_change,
        )
