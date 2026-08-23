"""Windows-safe SQLite storage for immutable central policies and kill history."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from algo_manus.domain.risk_controls import KillSwitchChange
from algo_manus.domain.risk_engine import CentralRiskPolicy


class SqliteRiskControlRepository:
    _SCHEMA_COMPONENT = "risk_controls"
    _SCHEMA_VERSION = 1

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    component TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL
                )
                """
            )
            schema = connection.execute(
                "SELECT schema_version FROM schema_metadata WHERE component = ?", (self._SCHEMA_COMPONENT,)
            ).fetchone()
            if schema is None:
                connection.execute(
                    "INSERT INTO schema_metadata (component, schema_version) VALUES (?, ?)",
                    (self._SCHEMA_COMPONENT, self._SCHEMA_VERSION),
                )
            elif schema["schema_version"] != self._SCHEMA_VERSION:
                raise RuntimeError("unsupported risk controls schema version")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS central_risk_policies (
                    policy_version TEXT PRIMARY KEY,
                    max_quantity_per_order INTEGER NOT NULL,
                    max_notional_per_order REAL NOT NULL,
                    max_open_positions INTEGER NOT NULL,
                    persisted_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS kill_switch_changes (
                    change_id TEXT PRIMARY KEY,
                    active INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_kill_switch_changes_time ON kill_switch_changes (occurred_at DESC, change_id DESC)"
            )

    def save_policy(self, policy: CentralRiskPolicy, *, persisted_at: datetime) -> None:
        if persisted_at.tzinfo is None:
            raise ValueError("risk policy persistence timestamp must be timezone-aware")
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT * FROM central_risk_policies WHERE policy_version = ?", (policy.policy_version,)
            ).fetchone()
            if existing is not None:
                restored = CentralRiskPolicy(
                    policy_version=existing["policy_version"],
                    max_quantity_per_order=existing["max_quantity_per_order"],
                    max_notional_per_order=existing["max_notional_per_order"],
                    max_open_positions=existing["max_open_positions"],
                )
                if restored != policy:
                    raise ValueError("immutable central risk policy conflicts with existing version")
                return
            connection.execute(
                """
                INSERT INTO central_risk_policies
                (policy_version, max_quantity_per_order, max_notional_per_order, max_open_positions, persisted_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    policy.policy_version,
                    policy.max_quantity_per_order,
                    policy.max_notional_per_order,
                    policy.max_open_positions,
                    persisted_at.isoformat(),
                ),
            )

    def get_policy(self, policy_version: str) -> tuple[CentralRiskPolicy, datetime] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM central_risk_policies WHERE policy_version = ?", (policy_version,)
            ).fetchone()
        if row is None:
            return None
        return (
            CentralRiskPolicy(
                policy_version=row["policy_version"],
                max_quantity_per_order=row["max_quantity_per_order"],
                max_notional_per_order=row["max_notional_per_order"],
                max_open_positions=row["max_open_positions"],
            ),
            datetime.fromisoformat(row["persisted_at"]),
        )

    def append_kill_switch_change(self, change: KillSwitchChange) -> None:
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT * FROM kill_switch_changes WHERE change_id = ?", (change.change_id,)
            ).fetchone()
            if existing is not None:
                restored = KillSwitchChange(
                    change_id=existing["change_id"],
                    active=bool(existing["active"]),
                    reason=existing["reason"],
                    occurred_at=datetime.fromisoformat(existing["occurred_at"]),
                )
                if restored != change:
                    raise ValueError("immutable kill-switch change conflicts with existing record")
                return
            connection.execute(
                """
                INSERT INTO kill_switch_changes (change_id, active, reason, occurred_at)
                VALUES (?, ?, ?, ?)
                """,
                (change.change_id, int(change.active), change.reason, change.occurred_at.isoformat()),
            )

    def current_kill_switch_change(self) -> KillSwitchChange | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM kill_switch_changes ORDER BY occurred_at DESC, change_id DESC LIMIT 1"
            ).fetchone()
        return self._change_from_row(row) if row is not None else None

    def list_kill_switch_changes(self, limit: int = 50) -> tuple[KillSwitchChange, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM kill_switch_changes ORDER BY occurred_at DESC, change_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return tuple(self._change_from_row(row) for row in rows)

    @staticmethod
    def _change_from_row(row: sqlite3.Row) -> KillSwitchChange:
        return KillSwitchChange(
            change_id=row["change_id"],
            active=bool(row["active"]),
            reason=row["reason"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
        )
