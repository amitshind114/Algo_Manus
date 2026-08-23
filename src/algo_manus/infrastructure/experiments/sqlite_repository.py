"""SQLite persistence for immutable experiment batch summaries."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from algo_manus.domain.backtest import BacktestMetrics, BacktestResult, BacktestSpec
from algo_manus.domain.experiment import (
    ExperimentBatch,
    ExperimentStatus,
    SecurityExperimentResult,
)


class SqliteExperimentBatchRepository:
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
                CREATE TABLE IF NOT EXISTS experiment_batches (
                    batch_id TEXT PRIMARY KEY,
                    universe_id TEXT NOT NULL,
                    universe_snapshot_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    parameter_revision_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    research_manifest_id TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(experiment_batches)").fetchall()
            }
            if "research_manifest_id" not in columns:
                connection.execute("ALTER TABLE experiment_batches ADD COLUMN research_manifest_id TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiment_results (
                    batch_id TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    spec_id TEXT NOT NULL,
                    initial_cash REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    commission_bps REAL NOT NULL,
                    slippage_bps REAL NOT NULL,
                    force_close_at_end INTEGER NOT NULL,
                    net_pnl REAL NOT NULL,
                    total_return_pct REAL NOT NULL,
                    max_drawdown_pct REAL NOT NULL,
                    trade_count INTEGER NOT NULL,
                    win_rate_pct REAL NOT NULL,
                    profit_factor REAL,
                    data_quality_note TEXT NOT NULL,
                    PRIMARY KEY (batch_id, instrument_id),
                    FOREIGN KEY (batch_id) REFERENCES experiment_batches(batch_id)
                )
                """
            )

    def save(self, batch: ExperimentBatch) -> None:
        with self._connection() as connection:
            if connection.execute("SELECT 1 FROM experiment_batches WHERE batch_id = ?", (batch.batch_id,)).fetchone():
                return
            connection.execute(
                """
                INSERT INTO experiment_batches
                (batch_id, universe_id, universe_snapshot_id, strategy_id, parameter_revision_id, created_at, status, research_manifest_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.batch_id,
                    batch.universe_id,
                    batch.universe_snapshot_id,
                    batch.strategy_id,
                    batch.parameter_revision_id,
                    batch.created_at.isoformat(),
                    batch.status.value,
                    batch.research_manifest_id,
                ),
            )
            connection.executemany(
                """
                INSERT INTO experiment_results
                (batch_id, instrument_id, dataset_id, spec_id, initial_cash, quantity,
                 commission_bps, slippage_bps, force_close_at_end, net_pnl, total_return_pct,
                 max_drawdown_pct, trade_count, win_rate_pct, profit_factor, data_quality_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        batch.batch_id,
                        item.instrument_id,
                        item.dataset_id,
                        item.backtest.spec.spec_id,
                        item.backtest.spec.initial_cash,
                        item.backtest.spec.quantity,
                        item.backtest.spec.commission_bps,
                        item.backtest.spec.slippage_bps,
                        int(item.backtest.spec.force_close_at_end),
                        item.backtest.metrics.net_pnl,
                        item.backtest.metrics.total_return_pct,
                        item.backtest.metrics.max_drawdown_pct,
                        item.backtest.metrics.trade_count,
                        item.backtest.metrics.win_rate_pct,
                        item.backtest.metrics.profit_factor,
                        item.data_quality_note,
                    )
                    for item in batch.results
                ],
            )

    def get(self, batch_id: str) -> ExperimentBatch | None:
        with self._connection() as connection:
            batch_row = connection.execute("SELECT * FROM experiment_batches WHERE batch_id = ?", (batch_id,)).fetchone()
            if batch_row is None:
                return None
            result_rows = connection.execute(
                "SELECT * FROM experiment_results WHERE batch_id = ? ORDER BY instrument_id", (batch_id,)
            ).fetchall()
        results = tuple(
            SecurityExperimentResult(
                instrument_id=row["instrument_id"],
                dataset_id=row["dataset_id"],
                backtest=BacktestResult(
                    spec=BacktestSpec(
                        dataset_id=row["dataset_id"],
                        strategy_id=batch_row["strategy_id"],
                        parameter_revision_id=batch_row["parameter_revision_id"],
                        initial_cash=row["initial_cash"],
                        quantity=row["quantity"],
                        commission_bps=row["commission_bps"],
                        slippage_bps=row["slippage_bps"],
                        force_close_at_end=bool(row["force_close_at_end"]),
                    ),
                    trades=(),
                    equity_curve=(),
                    metrics=BacktestMetrics(
                        net_pnl=row["net_pnl"],
                        total_return_pct=row["total_return_pct"],
                        max_drawdown_pct=row["max_drawdown_pct"],
                        trade_count=row["trade_count"],
                        win_rate_pct=row["win_rate_pct"],
                        profit_factor=row["profit_factor"],
                    ),
                ),
                data_quality_note=row["data_quality_note"],
            )
            for row in result_rows
        )
        return ExperimentBatch(
            batch_id=batch_row["batch_id"],
            universe_id=batch_row["universe_id"],
            universe_snapshot_id=batch_row["universe_snapshot_id"],
            strategy_id=batch_row["strategy_id"],
            parameter_revision_id=batch_row["parameter_revision_id"],
            created_at=datetime.fromisoformat(batch_row["created_at"]),
            status=ExperimentStatus(batch_row["status"]),
            results=results,
            research_manifest_id=batch_row["research_manifest_id"],
        )
