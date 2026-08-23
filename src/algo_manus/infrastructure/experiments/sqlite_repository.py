"""SQLite persistence for immutable experiment batch summaries."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from algo_manus.application.experiments import (
    ExperimentArtifactIntegrity,
    ExperimentArtifactIntegrityStatus,
    ExperimentResultArtifacts,
)
from algo_manus.domain.backtest import BacktestMetrics, BacktestResult, BacktestSpec, BacktestTrade
from algo_manus.domain.experiment import (
    ExperimentBatch,
    ExperimentStatus,
    SecurityExperimentResult,
)


class SqliteExperimentBatchRepository:
    def __init__(
        self,
        database_path: Path,
        *,
        max_equity_points_per_result: int = 5_000,
        max_trades_per_result: int = 5_000,
    ) -> None:
        if max_equity_points_per_result <= 0 or max_trades_per_result <= 0:
            raise ValueError("artifact retention limits must be positive")
        self._database_path = database_path
        self._max_equity_points_per_result = max_equity_points_per_result
        self._max_trades_per_result = max_trades_per_result
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
                    cagr_pct REAL,
                    sharpe_ratio REAL,
                    sortino_ratio REAL,
                    expectancy REAL,
                    turnover_pct REAL,
                    exposure_pct REAL,
                    average_holding_period_days REAL,
                    data_quality_note TEXT NOT NULL,
                    PRIMARY KEY (batch_id, instrument_id),
                    FOREIGN KEY (batch_id) REFERENCES experiment_batches(batch_id)
                )
                """
            )
            result_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(experiment_results)").fetchall()
            }
            for column in (
                "cagr_pct",
                "sharpe_ratio",
                "sortino_ratio",
                "expectancy",
                "turnover_pct",
                "exposure_pct",
                "average_holding_period_days",
            ):
                if column not in result_columns:
                    connection.execute(f"ALTER TABLE experiment_results ADD COLUMN {column} REAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiment_result_artifacts (
                    batch_id TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    result_spec_id TEXT NOT NULL,
                    trade_count INTEGER NOT NULL,
                    equity_point_count INTEGER NOT NULL,
                    PRIMARY KEY (batch_id, instrument_id),
                    FOREIGN KEY (batch_id, instrument_id)
                        REFERENCES experiment_results(batch_id, instrument_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiment_trades (
                    batch_id TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    gross_pnl REAL NOT NULL,
                    cost REAL NOT NULL,
                    PRIMARY KEY (batch_id, instrument_id, sequence),
                    FOREIGN KEY (batch_id, instrument_id)
                        REFERENCES experiment_result_artifacts(batch_id, instrument_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiment_equity_points (
                    batch_id TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    equity REAL NOT NULL,
                    PRIMARY KEY (batch_id, instrument_id, sequence),
                    FOREIGN KEY (batch_id, instrument_id)
                        REFERENCES experiment_result_artifacts(batch_id, instrument_id)
                )
                """
            )

    def save(self, batch: ExperimentBatch) -> None:
        self._validate_artifact_bounds(batch)
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
                 max_drawdown_pct, trade_count, win_rate_pct, profit_factor, cagr_pct, sharpe_ratio,
                 sortino_ratio, expectancy, turnover_pct, exposure_pct, average_holding_period_days, data_quality_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        item.backtest.metrics.cagr_pct,
                        item.backtest.metrics.sharpe_ratio,
                        item.backtest.metrics.sortino_ratio,
                        item.backtest.metrics.expectancy,
                        item.backtest.metrics.turnover_pct,
                        item.backtest.metrics.exposure_pct,
                        item.backtest.metrics.average_holding_period_days,
                        item.data_quality_note,
                    )
                    for item in batch.results
                ],
            )
            connection.executemany(
                """
                INSERT INTO experiment_result_artifacts
                (batch_id, instrument_id, result_spec_id, trade_count, equity_point_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        batch.batch_id,
                        item.instrument_id,
                        item.backtest.spec.spec_id,
                        len(item.backtest.trades),
                        len(item.backtest.equity_curve),
                    )
                    for item in batch.results
                ],
            )
            connection.executemany(
                """
                INSERT INTO experiment_trades
                (batch_id, instrument_id, sequence, entry_time, exit_time, quantity, entry_price, exit_price, gross_pnl, cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        batch.batch_id,
                        item.instrument_id,
                        sequence,
                        trade.entry_time.isoformat(),
                        trade.exit_time.isoformat(),
                        trade.quantity,
                        trade.entry_price,
                        trade.exit_price,
                        trade.gross_pnl,
                        trade.cost,
                    )
                    for item in batch.results
                    for sequence, trade in enumerate(item.backtest.trades)
                ],
            )
            connection.executemany(
                """
                INSERT INTO experiment_equity_points
                (batch_id, instrument_id, sequence, timestamp, equity)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        batch.batch_id,
                        item.instrument_id,
                        sequence,
                        timestamp.isoformat(),
                        equity,
                    )
                    for item in batch.results
                    for sequence, (timestamp, equity) in enumerate(item.backtest.equity_curve)
                ],
            )

    def get(self, batch_id: str) -> ExperimentBatch | None:
        return self._load(batch_id)

    def list_recent(self, limit: int = 20) -> tuple[ExperimentBatch, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            identifiers = connection.execute(
                "SELECT batch_id FROM experiment_batches ORDER BY created_at DESC, batch_id DESC LIMIT ?", (limit,)
            ).fetchall()
        batches = []
        for row in identifiers:
            batch = self._load(row["batch_id"])
            if batch is not None:
                batches.append(batch)
        return tuple(batches)

    def _load(self, batch_id: str) -> ExperimentBatch | None:
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
                        cagr_pct=row["cagr_pct"],
                        sharpe_ratio=row["sharpe_ratio"],
                        sortino_ratio=row["sortino_ratio"],
                        expectancy=row["expectancy"],
                        turnover_pct=row["turnover_pct"],
                        exposure_pct=row["exposure_pct"],
                        average_holding_period_days=row["average_holding_period_days"],
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

    def get_result_artifacts(
        self, *, batch_id: str, instrument_id: str
    ) -> ExperimentResultArtifacts | None:
        integrity = self.get_result_artifact_integrity(
            batch_id=batch_id, instrument_id=instrument_id
        )
        if integrity.status is ExperimentArtifactIntegrityStatus.UNAVAILABLE:
            return None
        if not integrity.is_complete:
            raise ValueError(f"persisted artifact integrity status is {integrity.status.value}")
        with self._connection() as connection:
            artifact = connection.execute(
                """
                SELECT result_spec_id, trade_count, equity_point_count
                FROM experiment_result_artifacts
                WHERE batch_id = ? AND instrument_id = ?
                """,
                (batch_id, instrument_id),
            ).fetchone()
            if artifact is None:
                return None
            trade_rows = connection.execute(
                """
                SELECT entry_time, exit_time, quantity, entry_price, exit_price, gross_pnl, cost
                FROM experiment_trades
                WHERE batch_id = ? AND instrument_id = ?
                ORDER BY sequence
                """,
                (batch_id, instrument_id),
            ).fetchall()
            equity_rows = connection.execute(
                """
                SELECT timestamp, equity FROM experiment_equity_points
                WHERE batch_id = ? AND instrument_id = ?
                ORDER BY sequence
                """,
                (batch_id, instrument_id),
            ).fetchall()
        return ExperimentResultArtifacts(
            batch_id=batch_id,
            instrument_id=instrument_id,
            result_spec_id=artifact["result_spec_id"],
            trades=tuple(
                BacktestTrade(
                    entry_time=datetime.fromisoformat(row["entry_time"]),
                    exit_time=datetime.fromisoformat(row["exit_time"]),
                    quantity=row["quantity"],
                    entry_price=row["entry_price"],
                    exit_price=row["exit_price"],
                    gross_pnl=row["gross_pnl"],
                    cost=row["cost"],
                )
                for row in trade_rows
            ),
            equity_curve=tuple(
                (datetime.fromisoformat(row["timestamp"]), row["equity"])
                for row in equity_rows
            ),
        )

    def get_result_artifact_integrity(
        self, *, batch_id: str, instrument_id: str
    ) -> ExperimentArtifactIntegrity:
        with self._connection() as connection:
            result = connection.execute(
                """
                SELECT spec_id FROM experiment_results
                WHERE batch_id = ? AND instrument_id = ?
                """,
                (batch_id, instrument_id),
            ).fetchone()
            if result is None:
                return ExperimentArtifactIntegrity(
                    batch_id=batch_id,
                    instrument_id=instrument_id,
                    status=ExperimentArtifactIntegrityStatus.UNAVAILABLE,
                    result_spec_id=None,
                    artifact_result_spec_id=None,
                    expected_trade_count=None,
                    actual_trade_count=0,
                    expected_equity_point_count=None,
                    actual_equity_point_count=0,
                )
            artifact = connection.execute(
                """
                SELECT result_spec_id, trade_count, equity_point_count
                FROM experiment_result_artifacts
                WHERE batch_id = ? AND instrument_id = ?
                """,
                (batch_id, instrument_id),
            ).fetchone()
            if artifact is None:
                return ExperimentArtifactIntegrity(
                    batch_id=batch_id,
                    instrument_id=instrument_id,
                    status=ExperimentArtifactIntegrityStatus.UNAVAILABLE,
                    result_spec_id=result["spec_id"],
                    artifact_result_spec_id=None,
                    expected_trade_count=None,
                    actual_trade_count=0,
                    expected_equity_point_count=None,
                    actual_equity_point_count=0,
                )
            actual_trade_count = connection.execute(
                """
                SELECT COUNT(*) FROM experiment_trades
                WHERE batch_id = ? AND instrument_id = ?
                """,
                (batch_id, instrument_id),
            ).fetchone()[0]
            actual_equity_point_count = connection.execute(
                """
                SELECT COUNT(*) FROM experiment_equity_points
                WHERE batch_id = ? AND instrument_id = ?
                """,
                (batch_id, instrument_id),
            ).fetchone()[0]
        status = ExperimentArtifactIntegrityStatus.COMPLETE
        if artifact["result_spec_id"] != result["spec_id"]:
            status = ExperimentArtifactIntegrityStatus.RESULT_SPEC_MISMATCH
        elif (
            actual_trade_count != artifact["trade_count"]
            or actual_equity_point_count != artifact["equity_point_count"]
        ):
            status = ExperimentArtifactIntegrityStatus.INCOMPLETE
        return ExperimentArtifactIntegrity(
            batch_id=batch_id,
            instrument_id=instrument_id,
            status=status,
            result_spec_id=result["spec_id"],
            artifact_result_spec_id=artifact["result_spec_id"],
            expected_trade_count=artifact["trade_count"],
            actual_trade_count=actual_trade_count,
            expected_equity_point_count=artifact["equity_point_count"],
            actual_equity_point_count=actual_equity_point_count,
        )

    def _validate_artifact_bounds(self, batch: ExperimentBatch) -> None:
        for item in batch.results:
            if len(item.backtest.equity_curve) > self._max_equity_points_per_result:
                raise ValueError("equity point retention limit exceeded")
            if len(item.backtest.trades) > self._max_trades_per_result:
                raise ValueError("trade retention limit exceeded")
