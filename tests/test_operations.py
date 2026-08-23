from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from algo_manus.application.operations import LocalOperationsService
from algo_manus.domain.operations import AuditRecord, HealthStatus, RuntimeMode
from algo_manus.infrastructure.audit.sqlite_audit import SqliteAuditTrail


class OperationsTests(unittest.TestCase):
    def test_audit_redacts_credentials_and_preserves_operational_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            trail = SqliteAuditTrail(Path(temporary) / "audit.sqlite3")
            trail.append(
                AuditRecord(
                    event_id="audit-1",
                    occurred_at=datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc),
                    category="local_operation",
                    action="configuration_checked",
                    correlation_id="run-1",
                    payload={"instrument_id": "ANGEL_ONE:NSE:NSE:500325", "api_token": "never-store"},
                )
            )
            latest = trail.latest()

        self.assertEqual(latest[0].payload["instrument_id"], "ANGEL_ONE:NSE:NSE:500325")
        self.assertEqual(latest[0].payload["api_token"], "[REDACTED]")

    def test_health_reports_live_and_broker_gates_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = LocalOperationsService().health_snapshot(
                data_dir=Path(temporary), mode=RuntimeMode.RESEARCH
            )
        statuses = {item.component: item.status for item in snapshot.components}

        self.assertEqual(statuses["local_data_directory"], HealthStatus.HEALTHY)
        self.assertEqual(statuses["broker_authentication"], HealthStatus.BLOCKED)
        self.assertEqual(statuses["live_execution"], HealthStatus.BLOCKED)


if __name__ == "__main__":
    unittest.main()
