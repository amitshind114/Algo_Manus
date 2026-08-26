"""Immutable local SQLite storage for Option K robustness evidence."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from algo_manus.application.robustness import (
    RobustnessCandidateEvidence,
    RobustnessEvidence,
    RobustnessGateState,
    RobustnessPartitionResult,
    RobustnessSplitPolicy,
)


class SqliteRobustnessEvidenceRepository:
    """Append-only local evidence storage; conflicting immutable IDs fail explicitly."""

    _SCHEMA_COMPONENT = "robustness_evidence"
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
                raise RuntimeError("unsupported robustness evidence schema version")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS robustness_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_robustness_evidence_created ON robustness_evidence (created_at DESC)"
            )

    def save(self, evidence: RobustnessEvidence) -> None:
        payload = self._serialize(evidence)
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT payload_json FROM robustness_evidence WHERE evidence_id = ?", (evidence.evidence_id,)
            ).fetchone()
            if existing is not None:
                if existing["payload_json"] != payload:
                    raise ValueError("immutable robustness evidence conflicts with existing record")
                return
            connection.execute(
                "INSERT INTO robustness_evidence (evidence_id, created_at, payload_json) VALUES (?, ?, ?)",
                (evidence.evidence_id, evidence.created_at.isoformat(), payload),
            )

    def get(self, evidence_id: str) -> RobustnessEvidence | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM robustness_evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
            return self._deserialize(row["payload_json"]) if row is not None else None

    def list_recent(self, limit: int = 20) -> tuple[RobustnessEvidence, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM robustness_evidence ORDER BY created_at DESC, evidence_id DESC LIMIT ?", (limit,)
            ).fetchall()
            return tuple(self._deserialize(row["payload_json"]) for row in rows)

    @staticmethod
    def _serialize(evidence: RobustnessEvidence) -> str:
        def partition(value: RobustnessPartitionResult | None):
            if value is None:
                return None
            return {
                "result_spec_id": value.result_spec_id,
                "net_pnl": value.net_pnl,
                "total_return_pct": value.total_return_pct,
                "trade_count": value.trade_count,
                "outcome": value.outcome,
                "next_bar_execution": value.next_bar_execution,
            }

        payload = {
            "evidence_id": evidence.evidence_id,
            "dataset_id": evidence.dataset_id,
            "strategy_id": evidence.strategy_id,
            "strategy_version": evidence.strategy_version,
            "split_policy": {
                "in_sample_ratio": evidence.split_policy.in_sample_ratio,
                "max_grid_cells": evidence.split_policy.max_grid_cells,
                "embargo_bars": evidence.split_policy.embargo_bars,
                "policy_version": evidence.split_policy.policy_version,
            },
            "in_sample_end": evidence.in_sample_end.isoformat(),
            "holdout_start": evidence.holdout_start.isoformat(),
            "gate_state": evidence.gate_state.value,
            "candidates": [
                {
                    "parameters": dict(item.parameters),
                    "parameter_revision_id": item.parameter_revision_id,
                    "in_sample": partition(item.in_sample),
                    "holdout": partition(item.holdout),
                    "status": item.status,
                }
                for item in evidence.candidates
            ],
            "initial_cash": evidence.initial_cash,
            "quantity": evidence.quantity,
            "commission_bps": evidence.commission_bps,
            "slippage_bps": evidence.slippage_bps,
            "force_close_at_end": evidence.force_close_at_end,
            "selection_bias_warning": evidence.selection_bias_warning,
            "created_at": evidence.created_at.isoformat(),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _deserialize(payload_json: str) -> RobustnessEvidence:
        payload = json.loads(payload_json)

        def partition(value):
            if value is None:
                return None
            return RobustnessPartitionResult(**value)

        return RobustnessEvidence(
            evidence_id=payload["evidence_id"],
            dataset_id=payload["dataset_id"],
            strategy_id=payload["strategy_id"],
            strategy_version=payload["strategy_version"],
            split_policy=RobustnessSplitPolicy(**payload["split_policy"]),
            in_sample_end=datetime.fromisoformat(payload["in_sample_end"]),
            holdout_start=datetime.fromisoformat(payload["holdout_start"]),
            gate_state=RobustnessGateState(payload["gate_state"]),
            candidates=tuple(
                RobustnessCandidateEvidence(
                    parameters=item["parameters"],
                    parameter_revision_id=item["parameter_revision_id"],
                    in_sample=partition(item["in_sample"]),
                    holdout=partition(item["holdout"]),
                    status=item["status"],
                )
                for item in payload["candidates"]
            ),
            initial_cash=payload["initial_cash"],
            quantity=payload["quantity"],
            commission_bps=payload["commission_bps"],
            slippage_bps=payload["slippage_bps"],
            force_close_at_end=payload["force_close_at_end"],
            selection_bias_warning=payload["selection_bias_warning"],
            created_at=datetime.fromisoformat(payload["created_at"]),
        )
