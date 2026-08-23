"""Read-only fixture experiment evidence export with integrity-gated detail."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from algo_manus.application.experiments import (
    ExperimentArtifactIntegrity,
    ExperimentArtifactReadService,
    ExperimentBatchRepository,
)
from algo_manus.domain.experiment import ExperimentBatch


class EvidenceExportRefusedError(ValueError):
    """Raised when detailed evidence export is not safe for the selected local batch."""


@dataclass(frozen=True, slots=True)
class ExperimentResultEvidenceExport:
    instrument_id: str
    dataset_id: str
    result_spec_id: str
    net_pnl: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    artifact_integrity: ExperimentArtifactIntegrity

    def summary_payload(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "dataset_id": self.dataset_id,
            "result_spec_id": self.result_spec_id,
            "net_pnl": self.net_pnl,
            "total_return_pct": self.total_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "trade_count": self.trade_count,
            "artifact_integrity": self.artifact_integrity.status.value,
            "actual_trade_count": self.artifact_integrity.actual_trade_count,
            "expected_trade_count": self.artifact_integrity.expected_trade_count,
            "actual_equity_point_count": self.artifact_integrity.actual_equity_point_count,
            "expected_equity_point_count": self.artifact_integrity.expected_equity_point_count,
            "result_spec_match": (
                self.artifact_integrity.result_spec_id
                == self.artifact_integrity.artifact_result_spec_id
            ),
        }


@dataclass(frozen=True, slots=True)
class ExperimentEvidenceExport:
    """A local fixture-evidence package; detailed contents are integrity-gated."""

    batch: ExperimentBatch
    results: tuple[ExperimentResultEvidenceExport, ...]
    _artifact_reader: ExperimentArtifactReadService

    _SUMMARY_SCHEMA = "algo-manus.local-evidence-summary"
    _DETAIL_SCHEMA = "algo-manus.local-evidence-detail"
    _SCHEMA_VERSION = 1

    @property
    def detailed_export_allowed(self) -> bool:
        return all(result.artifact_integrity.is_complete for result in self.results)

    def summary_payload(self) -> dict[str, Any]:
        return self._verified_payload(
            {
                "schema": self._SUMMARY_SCHEMA,
                "schema_version": self._SCHEMA_VERSION,
                "export_scope": "local_fixture_experiment_evidence",
                "fixture_only": True,
                "not_market_or_broker_evidence": True,
                "batch_id": self.batch.batch_id,
                "created_at": self.batch.created_at.isoformat(),
                "strategy_id": self.batch.strategy_id,
                "parameter_revision_id": self.batch.parameter_revision_id,
                "universe_id": self.batch.universe_id,
                "universe_snapshot_id": self.batch.universe_snapshot_id,
                "research_manifest_id": self.batch.research_manifest_id,
                "detailed_export_allowed": self.detailed_export_allowed,
                "results": [result.summary_payload() for result in self.results],
            }
        )

    def summary_json(self) -> str:
        return json.dumps(self.summary_payload(), indent=2, sort_keys=True)

    def detailed_json(self) -> str:
        return json.dumps(self.detailed_payload(), indent=2, sort_keys=True)

    def detailed_payload(self) -> dict[str, Any]:
        if not self.detailed_export_allowed:
            statuses = ", ".join(
                f"{result.instrument_id}:{result.artifact_integrity.status.value}"
                for result in self.results
                if not result.artifact_integrity.is_complete
            )
            raise EvidenceExportRefusedError(
                f"detailed local evidence export refused because artifact integrity is not complete: {statuses}"
            )
        details = []
        for result in self.results:
            artifacts = self._artifact_reader.get(
                batch_id=self.batch.batch_id,
                instrument_id=result.instrument_id,
            )
            details.append(
                {
                    "instrument_id": result.instrument_id,
                    "dataset_id": result.dataset_id,
                    "result_spec_id": artifacts.result_spec_id,
                    "equity_curve": [
                        {"timestamp": timestamp.isoformat(), "equity": equity}
                        for timestamp, equity in artifacts.equity_curve
                    ],
                    "trades": [
                        {
                            "entry_time": trade.entry_time.isoformat(),
                            "exit_time": trade.exit_time.isoformat(),
                            "quantity": trade.quantity,
                            "entry_price": trade.entry_price,
                            "exit_price": trade.exit_price,
                            "gross_pnl": trade.gross_pnl,
                            "cost": trade.cost,
                            "net_pnl": trade.net_pnl,
                        }
                        for trade in artifacts.trades
                    ],
                }
            )
        return self._verified_payload(
            {
                "schema": self._DETAIL_SCHEMA,
                "schema_version": self._SCHEMA_VERSION,
                "export_scope": "local_fixture_experiment_detail",
                "fixture_only": True,
                "not_market_or_broker_evidence": True,
                "batch_id": self.batch.batch_id,
                "research_manifest_id": self.batch.research_manifest_id,
                "results": details,
            }
        )

    @staticmethod
    def _verified_payload(payload: dict[str, Any]) -> dict[str, Any]:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return {
            **payload,
            "verification": {
                "algorithm": "sha256",
                "canonicalization": "utf-8 JSON, sort_keys=true, separators=(',', ':'), verification excluded",
                "sha256": sha256(canonical).hexdigest(),
            },
        }


class ExperimentEvidenceExportService:
    """Build read-only local evidence packages from persisted experiment records."""

    def __init__(self, repository: ExperimentBatchRepository) -> None:
        self._repository = repository
        self._artifact_reader = ExperimentArtifactReadService(repository)

    def get(self, *, batch_id: str) -> ExperimentEvidenceExport | None:
        batch = self._repository.get(batch_id)
        if batch is None:
            return None
        results = tuple(
            ExperimentResultEvidenceExport(
                instrument_id=item.instrument_id,
                dataset_id=item.dataset_id,
                result_spec_id=item.backtest.spec.spec_id,
                net_pnl=item.backtest.metrics.net_pnl,
                total_return_pct=item.backtest.metrics.total_return_pct,
                max_drawdown_pct=item.backtest.metrics.max_drawdown_pct,
                trade_count=item.backtest.metrics.trade_count,
                artifact_integrity=self._artifact_reader.integrity(
                    batch_id=batch.batch_id,
                    instrument_id=item.instrument_id,
                ),
            )
            for item in batch.results
        )
        return ExperimentEvidenceExport(
            batch=batch,
            results=results,
            _artifact_reader=self._artifact_reader,
        )
