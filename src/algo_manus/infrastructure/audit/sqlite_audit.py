"""Immutable local audit storage that redacts credential-like payload fields."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Mapping

from algo_manus.domain.operations import AuditRecord

_SENSITIVE_TOKENS = ("secret", "password", "token", "api_key", "apikey", "credential", "totp")


def redact_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Retain operational context without persisting obvious credentials."""
    return {
        key: "[REDACTED]" if any(token in key.lower() for token in _SENSITIVE_TOKENS) else value
        for key, value in payload.items()
    }


class SqliteAuditTrail:
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
                CREATE TABLE IF NOT EXISTS audit_records (
                    event_id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def append(self, record: AuditRecord) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_records
                (event_id, occurred_at, category, action, correlation_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_id,
                    record.occurred_at.isoformat(),
                    record.category,
                    record.action,
                    record.correlation_id,
                    json.dumps(redact_payload(record.payload), sort_keys=True),
                ),
            )

    def latest(self, limit: int = 50) -> tuple[AuditRecord, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_records ORDER BY occurred_at DESC, event_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return tuple(
            AuditRecord(
                event_id=row["event_id"],
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
                category=row["category"],
                action=row["action"],
                correlation_id=row["correlation_id"],
                payload=json.loads(row["payload_json"]),
            )
            for row in rows
        )
