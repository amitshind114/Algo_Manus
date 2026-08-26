"""Immutable SQLite retention for local dataset review evidence."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from algo_manus.application.dataset_review_gate import (
    DatasetReviewDeclaration,
    DatasetReviewDisposition,
    DatasetReviewEvidence,
    DatasetReviewGateState,
)


class SqliteDatasetReviewEvidenceRepository:
    """Append-only local review evidence; conflicts under one ID fail explicitly."""

    _SCHEMA_COMPONENT = "dataset_review_evidence"
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
                raise RuntimeError("unsupported dataset review evidence schema version")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_review_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    evaluated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_dataset_review_evidence_created ON dataset_review_evidence (evaluated_at DESC)"
            )

    def save(self, evidence: DatasetReviewEvidence) -> None:
        payload = self._serialize(evidence)
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT payload_json FROM dataset_review_evidence WHERE evidence_id = ?", (evidence.evidence_id,)
            ).fetchone()
            if existing is not None:
                if existing["payload_json"] != payload:
                    raise ValueError("immutable dataset review evidence conflicts with existing record")
                return
            connection.execute(
                "INSERT INTO dataset_review_evidence (evidence_id, evaluated_at, payload_json) VALUES (?, ?, ?)",
                (evidence.evidence_id, evidence.evaluated_at.isoformat(), payload),
            )

    def get(self, evidence_id: str) -> DatasetReviewEvidence | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM dataset_review_evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
            return self._deserialize(row["payload_json"]) if row is not None else None

    def list_recent(self, limit: int = 20) -> tuple[DatasetReviewEvidence, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM dataset_review_evidence ORDER BY evaluated_at DESC, evidence_id DESC LIMIT ?", (limit,)
            ).fetchall()
            return tuple(self._deserialize(row["payload_json"]) for row in rows)

    @staticmethod
    def _declaration_payload(declaration: DatasetReviewDeclaration | None) -> dict[str, str] | None:
        if declaration is None:
            return None
        return {
            "disposition": declaration.disposition.value,
            "scope_start": declaration.scope_start.isoformat(),
            "scope_end": declaration.scope_end.isoformat(),
            "source_reference": declaration.source_reference,
            "reviewed_at": declaration.reviewed_at.isoformat(),
            "note": declaration.note,
        }

    @classmethod
    def _serialize(cls, evidence: DatasetReviewEvidence) -> str:
        return json.dumps(
            {
                "evidence_id": evidence.evidence_id,
                "state": evidence.state.value,
                "dataset_id": evidence.dataset_id,
                "instrument_id": evidence.instrument_id,
                "interval": evidence.interval,
                "provenance_raw_content_sha256": evidence.provenance_raw_content_sha256,
                "adjustment_basis": evidence.adjustment_basis,
                "corporate_action_review": cls._declaration_payload(evidence.corporate_action_review),
                "calendar_review": cls._declaration_payload(evidence.calendar_review),
                "policy_version": evidence.policy_version,
                "blocking_reasons": list(evidence.blocking_reasons),
                "evaluated_at": evidence.evaluated_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _declaration(payload: dict[str, str] | None) -> DatasetReviewDeclaration | None:
        if payload is None:
            return None
        return DatasetReviewDeclaration(
            disposition=DatasetReviewDisposition(payload["disposition"]),
            scope_start=datetime.fromisoformat(payload["scope_start"]),
            scope_end=datetime.fromisoformat(payload["scope_end"]),
            source_reference=payload["source_reference"],
            reviewed_at=datetime.fromisoformat(payload["reviewed_at"]),
            note=payload["note"],
        )

    @classmethod
    def _deserialize(cls, payload_json: str) -> DatasetReviewEvidence:
        payload = json.loads(payload_json)
        return DatasetReviewEvidence(
            evidence_id=payload["evidence_id"],
            state=DatasetReviewGateState(payload["state"]),
            dataset_id=payload["dataset_id"],
            instrument_id=payload["instrument_id"],
            interval=payload["interval"],
            provenance_raw_content_sha256=payload["provenance_raw_content_sha256"],
            adjustment_basis=payload["adjustment_basis"],
            corporate_action_review=cls._declaration(payload["corporate_action_review"]),
            calendar_review=cls._declaration(payload["calendar_review"]),
            policy_version=payload["policy_version"],
            blocking_reasons=tuple(payload["blocking_reasons"]),
            evaluated_at=datetime.fromisoformat(payload["evaluated_at"]),
        )
