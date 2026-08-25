"""SQLite persistence for immutable, source-aware candle datasets."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from algo_manus.domain.market_data import (
    Candle,
    CandleDataset,
    DataProvenance,
    DataSourceKind,
    DataUseCase,
)


class SqliteCandleDatasetRepository:
    """Persists datasets immutably and closes every SQLite handle explicitly."""

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
                CREATE TABLE IF NOT EXISTS candle_datasets (
                    dataset_id TEXT PRIMARY KEY,
                    instrument_id TEXT NOT NULL,
                    interval_name TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    raw_content_sha256 TEXT NOT NULL,
                    adjustment_basis TEXT NOT NULL,
                    use_case TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_candles (
                    dataset_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume REAL NOT NULL,
                    PRIMARY KEY (dataset_id, timestamp),
                    FOREIGN KEY (dataset_id) REFERENCES candle_datasets(dataset_id)
                )
                """
            )

    def save(self, dataset: CandleDataset) -> None:
        with self._connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM candle_datasets WHERE dataset_id = ?", (dataset.dataset_id,)
            ).fetchone()
            if exists is not None:
                return
            provenance = dataset.provenance
            connection.execute(
                """
                INSERT INTO candle_datasets
                (dataset_id, instrument_id, interval_name, source_name, source_kind, source_uri,
                 retrieved_at, raw_content_sha256, adjustment_basis, use_case)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset.dataset_id,
                    dataset.instrument_id,
                    dataset.interval,
                    provenance.source_name,
                    provenance.source_kind.value,
                    provenance.source_uri,
                    provenance.retrieved_at.isoformat(),
                    provenance.raw_content_sha256,
                    provenance.adjustment_basis,
                    provenance.use_case.value,
                ),
            )
            connection.executemany(
                """
                INSERT INTO dataset_candles
                (dataset_id, timestamp, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        dataset.dataset_id,
                        candle.timestamp.isoformat(),
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                    )
                    for candle in dataset.candles
                ],
            )

    def get(self, dataset_id: str) -> CandleDataset | None:
        with self._connection() as connection:
            dataset_row = connection.execute(
                "SELECT * FROM candle_datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            if dataset_row is None:
                return None
            candle_rows = connection.execute(
                "SELECT * FROM dataset_candles WHERE dataset_id = ? ORDER BY timestamp", (dataset_id,)
            ).fetchall()
        return CandleDataset(
            dataset_id=dataset_row["dataset_id"],
            instrument_id=dataset_row["instrument_id"],
            interval=dataset_row["interval_name"],
            provenance=DataProvenance(
                source_name=dataset_row["source_name"],
                source_kind=DataSourceKind(dataset_row["source_kind"]),
                source_uri=dataset_row["source_uri"],
                retrieved_at=datetime.fromisoformat(dataset_row["retrieved_at"]),
                raw_content_sha256=dataset_row["raw_content_sha256"],
                adjustment_basis=dataset_row["adjustment_basis"],
                use_case=DataUseCase(dataset_row["use_case"]),
            ),
            candles=tuple(
                Candle(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    open=row["open_price"],
                    high=row["high_price"],
                    low=row["low_price"],
                    close=row["close_price"],
                    volume=row["volume"],
                )
                for row in candle_rows
            ),
        )

    def latest(self, *, source_name: str) -> CandleDataset | None:
        """Return the newest retained dataset for one source without refreshing it."""

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT dataset_id
                FROM candle_datasets
                WHERE source_name = ?
                ORDER BY retrieved_at DESC, dataset_id DESC
                LIMIT 1
                """,
                (source_name,),
            ).fetchone()
        return self.get(row["dataset_id"]) if row is not None else None

    def list_recent(self, *, source_name: str, limit: int = 20) -> tuple[CandleDataset, ...]:
        """List bounded immutable retained datasets for one source without refreshing it."""

        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT dataset_id
                FROM candle_datasets
                WHERE source_name = ?
                ORDER BY retrieved_at DESC, dataset_id DESC
                LIMIT ?
                """,
                (source_name, limit),
            ).fetchall()
        return tuple(
            dataset
            for row in rows
            if (dataset := self.get(row["dataset_id"])) is not None
        )
