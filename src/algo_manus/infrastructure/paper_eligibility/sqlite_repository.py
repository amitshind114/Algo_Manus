"""Immutable SQLite repository for local paper-run eligibility evidence."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from algo_manus.application.paper_run_eligibility import (
    PaperRunEligibilityEvidence,
    PaperRunEligibilityState,
)


class SqlitePaperRunEligibilityEvidenceRepository:
    """Append-only local evidence storage; conflicting immutable IDs fail explicitly."""

    _SCHEMA_COMPONENT = "paper_run_eligibility_evidence"
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
                "CREATE TABLE IF NOT EXISTS schema_metadata (component TEXT PRIMARY KEY, schema_version INTEGER NOT NULL)"
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
                raise RuntimeError("unsupported paper-run eligibility evidence schema version")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_run_eligibility_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    evaluated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_paper_run_eligibility_created ON paper_run_eligibility_evidence (evaluated_at DESC)"
            )

    def save(self, evidence: PaperRunEligibilityEvidence) -> None:
        payload = self._serialize(evidence)
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT payload_json FROM paper_run_eligibility_evidence WHERE evidence_id = ?", (evidence.evidence_id,)
            ).fetchone()
            if existing is not None:
                if existing["payload_json"] != payload:
                    raise ValueError("immutable paper-run eligibility evidence conflicts with existing record")
                return
            connection.execute(
                "INSERT INTO paper_run_eligibility_evidence (evidence_id, evaluated_at, payload_json) VALUES (?, ?, ?)",
                (evidence.evidence_id, evidence.evaluated_at.isoformat(), payload),
            )

    def get(self, evidence_id: str) -> PaperRunEligibilityEvidence | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM paper_run_eligibility_evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
            return self._deserialize(row["payload_json"]) if row is not None else None

    def list_recent(self, limit: int = 20) -> tuple[PaperRunEligibilityEvidence, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM paper_run_eligibility_evidence ORDER BY evaluated_at DESC, evidence_id DESC LIMIT ?", (limit,)
            ).fetchall()
            return tuple(self._deserialize(row["payload_json"]) for row in rows)

    @staticmethod
    def _serialize(evidence: PaperRunEligibilityEvidence) -> str:
        return json.dumps(
            {
                "evidence_id": evidence.evidence_id,
                "state": evidence.state.value,
                "batch_id": evidence.batch_id,
                "instrument_id": evidence.instrument_id,
                "manifest_id": evidence.manifest_id,
                "dataset_id": evidence.dataset_id,
                "strategy_id": evidence.strategy_id,
                "strategy_version": evidence.strategy_version,
                "parameter_revision_id": evidence.parameter_revision_id,
                "robustness_evidence_id": evidence.robustness_evidence_id,
                "policy_version": evidence.policy_version,
                "central_policy_version": evidence.central_policy_version,
                "kill_switch_change_id": evidence.kill_switch_change_id,
                "blocking_reasons": list(evidence.blocking_reasons),
                "evaluated_at": evidence.evaluated_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _deserialize(payload_json: str) -> PaperRunEligibilityEvidence:
        payload = json.loads(payload_json)
        return PaperRunEligibilityEvidence(
            evidence_id=payload["evidence_id"],
            state=PaperRunEligibilityState(payload["state"]),
            batch_id=payload["batch_id"],
            instrument_id=payload["instrument_id"],
            manifest_id=payload["manifest_id"],
            dataset_id=payload["dataset_id"],
            strategy_id=payload["strategy_id"],
            strategy_version=payload["strategy_version"],
            parameter_revision_id=payload["parameter_revision_id"],
            robustness_evidence_id=payload["robustness_evidence_id"],
            policy_version=payload["policy_version"],
            central_policy_version=payload["central_policy_version"],
            kill_switch_change_id=payload["kill_switch_change_id"],
            blocking_reasons=tuple(payload["blocking_reasons"]),
            evaluated_at=datetime.fromisoformat(payload["evaluated_at"]),
        )
