"""Local runtime controls and dependency-free health projection."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from algo_manus.domain.operations import (
    ComponentHealth,
    HealthStatus,
    LocalHealthSnapshot,
    RuntimeMode,
)


class LocalOperationsService:
    """Reports local readiness; it never starts services or accesses a broker."""

    def health_snapshot(self, *, data_dir: Path, mode: RuntimeMode) -> LocalHealthSnapshot:
        local_state = (
            ComponentHealth("local_data_directory", HealthStatus.HEALTHY, "local state directory available")
            if data_dir.exists()
            else ComponentHealth("local_data_directory", HealthStatus.DEGRADED, "local state directory has not been created")
        )
        broker_gate = ComponentHealth(
            "broker_authentication",
            HealthStatus.BLOCKED,
            "broker authentication is not implemented or enabled in the local build",
        )
        execution_gate = ComponentHealth(
            "live_execution",
            HealthStatus.BLOCKED,
            "live execution is unavailable by product design",
        )
        return LocalHealthSnapshot(
            observed_at=datetime.now(timezone.utc),
            mode=mode,
            components=(local_state, broker_gate, execution_gate),
        )
