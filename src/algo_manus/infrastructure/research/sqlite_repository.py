"""SQLite persistence for immutable local research manifests and validation evidence."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from algo_manus.domain.market_data import DataSourceKind, DataUseCase
from algo_manus.domain.research import (
    DataValidationIssue,
    DataValidationSeverity,
    DataValidationStatus,
    DatasetLineage,
    DatasetValidationOutcome,
    ResearchExecutionAssumptions,
    ResearchRunManifest,
)


class SqliteResearchEvidenceRepository:
    """One local database implementation of the manifest and validation ports.

    Rows are append-only at the logical-contract level: an existing immutable
    manifest or outcome is accepted only when the same value is saved again.
    A conflicting value under the same immutable key fails explicitly.
    """

    _SCHEMA_COMPONENT = "research_evidence"
    _SCHEMA_VERSION = 1

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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
            row = connection.execute(
                "SELECT schema_version FROM schema_metadata WHERE component = ?", (self._SCHEMA_COMPONENT,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO schema_metadata (component, schema_version) VALUES (?, ?)",
                    (self._SCHEMA_COMPONENT, self._SCHEMA_VERSION),
                )
            elif row["schema_version"] != self._SCHEMA_VERSION:
                raise RuntimeError("unsupported research evidence schema version")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_validation_outcomes (
                    dataset_id TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    validated_at TEXT NOT NULL,
                    PRIMARY KEY (dataset_id, policy_version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_validation_issues (
                    dataset_id TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    issue_index INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    PRIMARY KEY (dataset_id, policy_version, issue_index),
                    FOREIGN KEY (dataset_id, policy_version)
                        REFERENCES dataset_validation_outcomes (dataset_id, policy_version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_manifests (
                    manifest_id TEXT PRIMARY KEY,
                    universe_id TEXT NOT NULL,
                    universe_snapshot_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    parameter_revision_id TEXT NOT NULL,
                    engine_version TEXT NOT NULL,
                    initial_cash REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    commission_bps REAL NOT NULL,
                    slippage_bps REAL NOT NULL,
                    force_close_at_end INTEGER NOT NULL,
                    execution_timing TEXT NOT NULL,
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    information_cutoff TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    git_commit_sha TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_manifest_lineages (
                    manifest_id TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    raw_content_sha256 TEXT NOT NULL,
                    adjustment_basis TEXT NOT NULL,
                    use_case TEXT NOT NULL,
                    PRIMARY KEY (manifest_id, dataset_id),
                    FOREIGN KEY (manifest_id) REFERENCES research_manifests (manifest_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_manifest_validations (
                    manifest_id TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    PRIMARY KEY (manifest_id, dataset_id),
                    FOREIGN KEY (manifest_id) REFERENCES research_manifests (manifest_id),
                    FOREIGN KEY (dataset_id, policy_version)
                        REFERENCES dataset_validation_outcomes (dataset_id, policy_version)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_research_manifests_created ON research_manifests (created_at DESC)"
            )

    def save(self, manifest: ResearchRunManifest) -> None:
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT 1 FROM research_manifests WHERE manifest_id = ?", (manifest.manifest_id,)
            ).fetchone()
            if existing is not None:
                return
            for outcome in manifest.validation_outcomes:
                self._save_outcome(connection, outcome)
            assumptions = manifest.execution_assumptions
            connection.execute(
                """
                INSERT INTO research_manifests
                (manifest_id, universe_id, universe_snapshot_id, strategy_id, strategy_version,
                 parameter_revision_id, engine_version, initial_cash, quantity, commission_bps,
                 slippage_bps, force_close_at_end, execution_timing, start_at, end_at,
                 information_cutoff, created_at, git_commit_sha)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.manifest_id,
                    manifest.universe_id,
                    manifest.universe_snapshot_id,
                    manifest.strategy_id,
                    manifest.strategy_version,
                    manifest.parameter_revision_id,
                    manifest.engine_version,
                    assumptions.initial_cash,
                    assumptions.quantity,
                    assumptions.commission_bps,
                    assumptions.slippage_bps,
                    int(assumptions.force_close_at_end),
                    assumptions.execution_timing,
                    manifest.start.isoformat(),
                    manifest.end.isoformat(),
                    manifest.information_cutoff.isoformat(),
                    manifest.created_at.isoformat(),
                    manifest.git_commit_sha,
                ),
            )
            connection.executemany(
                """
                INSERT INTO research_manifest_lineages
                (manifest_id, dataset_id, instrument_id, interval, source_name, source_kind,
                 source_uri, retrieved_at, raw_content_sha256, adjustment_basis, use_case)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        manifest.manifest_id,
                        item.dataset_id,
                        item.instrument_id,
                        item.interval,
                        item.source_name,
                        item.source_kind.value,
                        item.source_uri,
                        item.retrieved_at.isoformat(),
                        item.raw_content_sha256,
                        item.adjustment_basis,
                        item.use_case.value,
                    )
                    for item in manifest.lineages
                ],
            )
            connection.executemany(
                """
                INSERT INTO research_manifest_validations (manifest_id, dataset_id, policy_version)
                VALUES (?, ?, ?)
                """,
                [
                    (manifest.manifest_id, item.dataset_id, item.policy_version)
                    for item in manifest.validation_outcomes
                ],
            )

    def get(self, manifest_id: str) -> ResearchRunManifest | None:
        with self._connection() as connection:
            return self._get_manifest(connection, manifest_id)

    def list_recent(self, limit: int = 20) -> tuple[ResearchRunManifest, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            identifiers = connection.execute(
                "SELECT manifest_id FROM research_manifests ORDER BY created_at DESC, manifest_id DESC LIMIT ?", (limit,)
            ).fetchall()
            return tuple(self._get_manifest(connection, row["manifest_id"]) for row in identifiers)

    def save_validation(self, outcome: DatasetValidationOutcome) -> None:
        with self._connection() as connection:
            self._save_outcome(connection, outcome)

    def get_validation(self, dataset_id: str, policy_version: str) -> DatasetValidationOutcome | None:
        with self._connection() as connection:
            return self._get_outcome(connection, dataset_id, policy_version)

    def _save_outcome(self, connection: sqlite3.Connection, outcome: DatasetValidationOutcome) -> None:
        existing = self._get_outcome(connection, outcome.dataset_id, outcome.policy_version)
        if existing is not None:
            if existing != outcome:
                raise ValueError("immutable validation outcome conflicts with existing record")
            return
        connection.execute(
            """
            INSERT INTO dataset_validation_outcomes (dataset_id, policy_version, status, validated_at)
            VALUES (?, ?, ?, ?)
            """,
            (outcome.dataset_id, outcome.policy_version, outcome.status.value, outcome.validated_at.isoformat()),
        )
        connection.executemany(
            """
            INSERT INTO dataset_validation_issues
            (dataset_id, policy_version, issue_index, code, severity, message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    outcome.dataset_id,
                    outcome.policy_version,
                    index,
                    issue.code,
                    issue.severity.value,
                    issue.message,
                )
                for index, issue in enumerate(outcome.issues)
            ],
        )

    def _get_manifest(self, connection: sqlite3.Connection, manifest_id: str) -> ResearchRunManifest | None:
        row = connection.execute(
            "SELECT * FROM research_manifests WHERE manifest_id = ?", (manifest_id,)
        ).fetchone()
        if row is None:
            return None
        lineage_rows = connection.execute(
            "SELECT * FROM research_manifest_lineages WHERE manifest_id = ? ORDER BY dataset_id", (manifest_id,)
        ).fetchall()
        validation_rows = connection.execute(
            "SELECT dataset_id, policy_version FROM research_manifest_validations WHERE manifest_id = ? ORDER BY dataset_id",
            (manifest_id,),
        ).fetchall()
        outcomes = tuple(
            self._get_outcome(connection, validation["dataset_id"], validation["policy_version"])
            for validation in validation_rows
        )
        if any(item is None for item in outcomes):
            raise RuntimeError("manifest references a missing validation outcome")
        return ResearchRunManifest(
            universe_id=row["universe_id"],
            universe_snapshot_id=row["universe_snapshot_id"],
            strategy_id=row["strategy_id"],
            strategy_version=row["strategy_version"],
            parameter_revision_id=row["parameter_revision_id"],
            engine_version=row["engine_version"],
            lineages=tuple(
                DatasetLineage(
                    dataset_id=item["dataset_id"],
                    instrument_id=item["instrument_id"],
                    interval=item["interval"],
                    source_name=item["source_name"],
                    source_kind=DataSourceKind(item["source_kind"]),
                    source_uri=item["source_uri"],
                    retrieved_at=datetime.fromisoformat(item["retrieved_at"]),
                    raw_content_sha256=item["raw_content_sha256"],
                    adjustment_basis=item["adjustment_basis"],
                    use_case=DataUseCase(item["use_case"]),
                )
                for item in lineage_rows
            ),
            validation_outcomes=tuple(item for item in outcomes if item is not None),
            execution_assumptions=ResearchExecutionAssumptions(
                initial_cash=row["initial_cash"],
                quantity=row["quantity"],
                commission_bps=row["commission_bps"],
                slippage_bps=row["slippage_bps"],
                force_close_at_end=bool(row["force_close_at_end"]),
                execution_timing=row["execution_timing"],
            ),
            start=datetime.fromisoformat(row["start_at"]),
            end=datetime.fromisoformat(row["end_at"]),
            information_cutoff=datetime.fromisoformat(row["information_cutoff"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            git_commit_sha=row["git_commit_sha"],
        )

    def _get_outcome(
        self, connection: sqlite3.Connection, dataset_id: str, policy_version: str
    ) -> DatasetValidationOutcome | None:
        row = connection.execute(
            """
            SELECT * FROM dataset_validation_outcomes
            WHERE dataset_id = ? AND policy_version = ?
            """,
            (dataset_id, policy_version),
        ).fetchone()
        if row is None:
            return None
        issue_rows = connection.execute(
            """
            SELECT * FROM dataset_validation_issues
            WHERE dataset_id = ? AND policy_version = ?
            ORDER BY issue_index
            """,
            (dataset_id, policy_version),
        ).fetchall()
        return DatasetValidationOutcome(
            dataset_id=row["dataset_id"],
            status=DataValidationStatus(row["status"]),
            policy_version=row["policy_version"],
            validated_at=datetime.fromisoformat(row["validated_at"]),
            issues=tuple(
                DataValidationIssue(
                    code=item["code"],
                    severity=DataValidationSeverity(item["severity"]),
                    message=item["message"],
                )
                for item in issue_rows
            ),
        )
