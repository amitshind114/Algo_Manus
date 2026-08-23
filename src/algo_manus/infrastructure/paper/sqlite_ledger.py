"""Append-only SQLite paper event ledger with explicit handle closure."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from algo_manus.domain.paper import PaperEvent, PaperEventType


class SqlitePaperLedger:
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
                CREATE TABLE IF NOT EXISTS paper_events (
                    event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_paper_events_order ON paper_events (order_id, occurred_at)"
            )

    def append(self, event: PaperEvent) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO paper_events
                (event_id, event_type, occurred_at, order_id, instrument_id, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type.value,
                    event.occurred_at.isoformat(),
                    event.order_id,
                    event.instrument_id,
                    event.payload,
                ),
            )

    def order_ids(self) -> frozenset[str]:
        with self._connection() as connection:
            rows = connection.execute("SELECT DISTINCT order_id FROM paper_events").fetchall()
        return frozenset(row["order_id"] for row in rows)

    def events_for(self, order_id: str) -> tuple[PaperEvent, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM paper_events WHERE order_id = ? ORDER BY event_sequence", (order_id,)
            ).fetchall()
        from datetime import datetime

        return tuple(
            PaperEvent(
                event_id=row["event_id"],
                event_type=PaperEventType(row["event_type"]),
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
                order_id=row["order_id"],
                instrument_id=row["instrument_id"],
                payload=row["payload"],
            )
            for row in rows
        )

    def events(self, limit: int = 1_000) -> tuple[PaperEvent, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM paper_events ORDER BY event_sequence ASC LIMIT ?", (limit,)
            ).fetchall()
        from datetime import datetime

        return tuple(
            PaperEvent(
                event_id=row["event_id"],
                event_type=PaperEventType(row["event_type"]),
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
                order_id=row["order_id"],
                instrument_id=row["instrument_id"],
                payload=row["payload"],
            )
            for row in rows
        )
