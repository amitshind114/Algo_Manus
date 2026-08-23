"""SQLite persistence for immutable normalized instrument-master snapshots."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from algo_manus.domain.instruments import (
    Instrument,
    InstrumentMasterSnapshot,
    InstrumentStatus,
    InstrumentType,
    OptionType,
)


class SqliteInstrumentSnapshotRepository:
    """Stores every accepted snapshot; never overwrites historic master data."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Yield one transaction and always close its OS-level file handle.

        ``sqlite3.Connection`` commits/rolls back when used as a context manager,
        but it does not close itself. Explicit closure matters on Windows, where an
        open database handle prevents temporary test directories from being removed.
        """
        connection = self._connect()
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
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS instrument_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    broker TEXT NOT NULL,
                    downloaded_at TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    UNIQUE (broker, content_sha256)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshot_instruments (
                    snapshot_id TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    broker TEXT NOT NULL,
                    exchange_name TEXT NOT NULL,
                    segment TEXT NOT NULL,
                    broker_token TEXT NOT NULL,
                    trading_symbol TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    instrument_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    expiry TEXT,
                    strike REAL,
                    option_type TEXT,
                    lot_size INTEGER,
                    tick_size REAL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (snapshot_id, instrument_id),
                    FOREIGN KEY (snapshot_id) REFERENCES instrument_snapshots(snapshot_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_broker_time "
                "ON instrument_snapshots (broker, downloaded_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS instrument_master_sync_state (
                    broker TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    last_checked_at TEXT NOT NULL,
                    FOREIGN KEY (snapshot_id) REFERENCES instrument_snapshots(snapshot_id)
                )
                """
            )

    def save(self, snapshot: InstrumentMasterSnapshot) -> None:
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT snapshot_id FROM instrument_snapshots WHERE snapshot_id = ?",
                (snapshot.snapshot_id,),
            ).fetchone()
            if existing is not None:
                return
            connection.execute(
                """
                INSERT INTO instrument_snapshots
                (snapshot_id, broker, downloaded_at, source_uri, content_sha256)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.broker,
                    snapshot.downloaded_at.isoformat(),
                    snapshot.source_uri,
                    snapshot.content_sha256,
                ),
            )
            for instrument in snapshot.instruments:
                connection.execute(
                    """
                    INSERT INTO snapshot_instruments
                    (snapshot_id, instrument_id, broker, exchange_name, segment,
                     broker_token, trading_symbol, display_name, instrument_type, status,
                     expiry, strike, option_type, lot_size, tick_size, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot.snapshot_id,
                        instrument.instrument_id,
                        instrument.broker,
                        instrument.exchange,
                        instrument.segment,
                        instrument.broker_token,
                        instrument.trading_symbol,
                        instrument.display_name,
                        instrument.instrument_type.value,
                        instrument.status.value,
                        instrument.expiry.isoformat() if instrument.expiry else None,
                        instrument.strike,
                        instrument.option_type.value if instrument.option_type else None,
                        instrument.lot_size,
                        instrument.tick_size,
                        json.dumps(dict(instrument.metadata), sort_keys=True),
                    ),
                )

    def latest(self, broker: str) -> InstrumentMasterSnapshot | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT snapshot_id FROM instrument_snapshots
                WHERE UPPER(broker) = UPPER(?)
                ORDER BY downloaded_at DESC
                LIMIT 1
                """,
                (broker,),
            ).fetchone()
        return self.get(row["snapshot_id"]) if row else None

    def find_by_content_hash(self, broker: str, content_sha256: str) -> InstrumentMasterSnapshot | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT snapshot_id FROM instrument_snapshots
                WHERE UPPER(broker) = UPPER(?) AND content_sha256 = ?
                """,
                (broker, content_sha256),
            ).fetchone()
        return self.get(row["snapshot_id"]) if row else None

    def last_checked_at(self, broker: str) -> datetime | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT last_checked_at FROM instrument_master_sync_state
                WHERE UPPER(broker) = UPPER(?)
                """,
                (broker,),
            ).fetchone()
        return datetime.fromisoformat(row["last_checked_at"]) if row else None

    def record_check(self, broker: str, snapshot_id: str, checked_at: datetime) -> None:
        if checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO instrument_master_sync_state (broker, snapshot_id, last_checked_at)
                VALUES (?, ?, ?)
                ON CONFLICT(broker) DO UPDATE SET
                    snapshot_id = excluded.snapshot_id,
                    last_checked_at = excluded.last_checked_at
                """,
                (broker, snapshot_id, checked_at.isoformat()),
            )

    def get(self, snapshot_id: str) -> InstrumentMasterSnapshot | None:
        with self._connection() as connection:
            snapshot_row = connection.execute(
                "SELECT * FROM instrument_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
            if snapshot_row is None:
                return None
            instrument_rows = connection.execute(
                "SELECT * FROM snapshot_instruments WHERE snapshot_id = ? ORDER BY instrument_id",
                (snapshot_id,),
            ).fetchall()
        return InstrumentMasterSnapshot(
            snapshot_id=snapshot_row["snapshot_id"],
            broker=snapshot_row["broker"],
            downloaded_at=datetime.fromisoformat(snapshot_row["downloaded_at"]),
            source_uri=snapshot_row["source_uri"],
            content_sha256=snapshot_row["content_sha256"],
            instruments=tuple(self._to_instrument(row) for row in instrument_rows),
        )

    @staticmethod
    def _to_instrument(row: sqlite3.Row) -> Instrument:
        return Instrument(
            broker=row["broker"],
            exchange=row["exchange_name"],
            segment=row["segment"],
            broker_token=row["broker_token"],
            trading_symbol=row["trading_symbol"],
            display_name=row["display_name"],
            instrument_type=InstrumentType(row["instrument_type"]),
            status=InstrumentStatus(row["status"]),
            expiry=date.fromisoformat(row["expiry"]) if row["expiry"] else None,
            strike=row["strike"],
            option_type=OptionType(row["option_type"]) if row["option_type"] else None,
            lot_size=row["lot_size"],
            tick_size=row["tick_size"],
            metadata=json.loads(row["metadata_json"]),
        )
