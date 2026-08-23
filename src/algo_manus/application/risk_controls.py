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

    def ensure_snapshot(
        self,
        policy: CentralRiskPolicy,
        *,
        initial_kill_reason: str,
        now: datetime | None = None,
    ) -> RiskControlSnapshot:
        """Initialize explicit local controls once, then return their durable snapshot."""

        occurred_at = now or datetime.now(timezone.utc)
        if self._repository.get_policy(policy.policy_version) is None:
            self._repository.save_policy(policy, persisted_at=occurred_at)
        if self._repository.current_kill_switch_change() is None:
            self.set_kill_switch(active=False, reason=initial_kill_reason, now=occurred_at)
        return self.snapshot(policy.policy_version)

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

    def kill_switch_history(self, limit: int = 20) -> tuple[KillSwitchChange, ...]:
        return self._repository.list_kill_switch_changes(limit)
