"""Deterministic read-only selected-evidence manifest generation.

The manifest is a local export view over already-retained evidence. It does not
write records, open references, retrieve data, or alter research, promotion,
risk, paper, provider, or execution state.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Protocol

from algo_manus.application.cross_evidence_linkage import LocalCrossEvidenceLinkageReadService
from algo_manus.application.dataset_review_gate import DatasetReviewEvidence
from algo_manus.application.experiment_evidence import ExperimentEvidenceReadService
from algo_manus.application.paper_run_eligibility import PaperRunEligibilityEvidence
from algo_manus.application.robustness import RobustnessEvidence


@dataclass(frozen=True, slots=True)
class RetainedEvidenceManifest:
    """Canonical local evidence payload and its SHA-256 hash; not an approval artifact."""

    payload: dict[str, Any]
    canonical_json: str
    manifest_sha256: str

    def json(self) -> str:
        """Return display/download JSON with canonical verification metadata included."""

        return json.dumps(self.payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)


class RobustnessEvidenceReadRepository(Protocol):
    def get(self, evidence_id: str) -> RobustnessEvidence | None: ...


class PaperRunEvidenceReadRepository(Protocol):
    def get(self, evidence_id: str) -> PaperRunEligibilityEvidence | None: ...

    def list_recent(self, limit: int = 20) -> tuple[PaperRunEligibilityEvidence, ...]: ...


class DatasetReviewEvidenceReadRepository(Protocol):
    def get(self, evidence_id: str) -> DatasetReviewEvidence | None: ...

    def list_recent(self, limit: int = 20) -> tuple[DatasetReviewEvidence, ...]: ...


class LocalRetainedEvidenceManifestService:
    """Build canonical manifests from selected retained evidence without mutations or fallback."""

    _SCHEMA = "algo-manus.retained-evidence-manifest"
    _SCHEMA_VERSION = 1
    _PAPER_READ_LIMIT = 64

    def __init__(
        self,
        research: ExperimentEvidenceReadService,
        robustness: RobustnessEvidenceReadRepository,
        paper_runs: PaperRunEvidenceReadRepository,
        dataset_reviews: DatasetReviewEvidenceReadRepository,
    ) -> None:
        self._research = research
        self._robustness = robustness
        self._paper_runs = paper_runs
        self._dataset_reviews = dataset_reviews
        self._linkage = LocalCrossEvidenceLinkageReadService(paper_runs, dataset_reviews)

    def build(
        self,
        *,
        batch_id: str,
        instrument_id: str,
        paper_run_evidence_id: str | None = None,
    ) -> RetainedEvidenceManifest:
        if not batch_id.strip() or not instrument_id.strip():
            raise ValueError("batch_id and instrument_id are required")
        conditions: list[str] = []
        view = self._research.get(batch_id)
        if view is None:
            conditions.append("RESEARCH_MANIFEST_EVIDENCE_MISSING")
            payload = self._base_payload(batch_id=batch_id, instrument_id=instrument_id, conditions=conditions)
            return self._verified(payload)

        batch = view.batch
        manifest = view.manifest
        result = next((item for item in batch.results if item.instrument_id == instrument_id), None)
        if result is None:
            conditions.append("BATCH_INSTRUMENT_EVIDENCE_MISSING")

        paper = self._paper_evidence(
            batch_id=batch_id,
            instrument_id=instrument_id,
            requested_evidence_id=paper_run_evidence_id,
            conditions=conditions,
        )
        robustness = self._robustness.get(paper.robustness_evidence_id) if paper and paper.robustness_evidence_id else None
        if paper is None:
            conditions.append("PAPER_RUN_EVIDENCE_MISSING")
            conditions.append("ROBUSTNESS_EVIDENCE_MISSING")
        else:
            conditions.extend(paper.blocking_reasons)
        if paper is not None and robustness is None:
            conditions.append("ROBUSTNESS_EVIDENCE_MISSING")

        review: DatasetReviewEvidence | None = None
        linkage_payload: dict[str, Any] | None = None
        if paper is not None:
            linkage = self._linkage.link(paper.evidence_id)
            review = self._dataset_reviews.get(linkage.dataset_review_evidence_id) if linkage.dataset_review_evidence_id else None
            conditions.extend(linkage.reasons)
            linkage_payload = {
                "state": linkage.state.value,
                "dataset_review_evidence_id": linkage.dataset_review_evidence_id,
                "conditions": list(linkage.reasons),
            }
            if review is None:
                conditions.append("DATASET_REVIEW_EVIDENCE_MISSING")
        else:
            conditions.append("DATASET_REVIEW_EVIDENCE_MISSING")

        payload = {
            "schema": self._SCHEMA,
            "schema_version": self._SCHEMA_VERSION,
            "export_scope": "selected_retained_local_evidence",
            "fixture_or_local_research_only": True,
            "not_market_broker_or_execution_evidence": True,
            "selection": {
                "batch_id": batch_id,
                "instrument_id": instrument_id,
                "paper_run_evidence_id": paper_run_evidence_id,
            },
            "experiment": {
                "batch_id": batch.batch_id,
                "created_at": batch.created_at.isoformat(),
                "status": batch.status.value,
                "universe_id": batch.universe_id,
                "universe_snapshot_id": batch.universe_snapshot_id,
                "strategy_id": batch.strategy_id,
                "parameter_revision_id": batch.parameter_revision_id,
                "research_manifest_id": batch.research_manifest_id,
            },
            "research_manifest": self._manifest_payload(manifest),
            "selected_evidence": {
                "result": self._result_payload(result),
                "paper_run": self._paper_payload(paper),
                "robustness": self._robustness_payload(robustness),
                "dataset_review": self._review_payload(review),
                "linkage": linkage_payload,
            },
            "conditions": sorted(set(conditions)),
            "secret_exclusion": {
                "manual_reference_contents_excluded": True,
                "review_notes_excluded": True,
                "source_uris_excluded": True,
                "credentials_and_tokens_excluded": True,
                "detailed_trades_and_equity_excluded": True,
            },
        }
        return self._verified(payload)

    def _paper_evidence(
        self,
        *,
        batch_id: str,
        instrument_id: str,
        requested_evidence_id: str | None,
        conditions: list[str],
    ) -> PaperRunEligibilityEvidence | None:
        matching = tuple(
            item
            for item in self._paper_runs.list_recent(self._PAPER_READ_LIMIT)
            if item.batch_id == batch_id and item.instrument_id == instrument_id
        )
        if requested_evidence_id is not None:
            requested = self._paper_runs.get(requested_evidence_id)
            if requested is None or requested not in matching:
                conditions.append("PAPER_RUN_EVIDENCE_ID_MISMATCH")
                return None
            return requested
        if len(matching) == 1:
            return matching[0]
        if len(matching) > 1:
            conditions.append("PAPER_RUN_EVIDENCE_SELECTION_REQUIRED")
        return None

    @classmethod
    def _base_payload(cls, *, batch_id: str, instrument_id: str, conditions: list[str]) -> dict[str, Any]:
        return {
            "schema": cls._SCHEMA,
            "schema_version": cls._SCHEMA_VERSION,
            "export_scope": "selected_retained_local_evidence",
            "fixture_or_local_research_only": True,
            "not_market_broker_or_execution_evidence": True,
            "selection": {"batch_id": batch_id, "instrument_id": instrument_id, "paper_run_evidence_id": None},
            "experiment": None,
            "research_manifest": None,
            "selected_evidence": {"result": None, "paper_run": None, "robustness": None, "dataset_review": None, "linkage": None},
            "conditions": sorted(set(conditions)),
            "secret_exclusion": {
                "manual_reference_contents_excluded": True,
                "review_notes_excluded": True,
                "source_uris_excluded": True,
                "credentials_and_tokens_excluded": True,
                "detailed_trades_and_equity_excluded": True,
            },
        }

    @staticmethod
    def _manifest_payload(manifest) -> dict[str, Any]:
        outcomes = {item.dataset_id: item for item in manifest.validation_outcomes}
        return {
            "manifest_id": manifest.manifest_id,
            "strategy_id": manifest.strategy_id,
            "strategy_version": manifest.strategy_version,
            "parameter_revision_id": manifest.parameter_revision_id,
            "engine_version": manifest.engine_version,
            "start": manifest.start.isoformat(),
            "end": manifest.end.isoformat(),
            "information_cutoff": manifest.information_cutoff.isoformat(),
            "lineages": [
                {
                    "dataset_id": lineage.dataset_id,
                    "instrument_id": lineage.instrument_id,
                    "interval": lineage.interval,
                    "source_name": lineage.source_name,
                    "source_kind": lineage.source_kind.value,
                    "retrieved_at": lineage.retrieved_at.isoformat(),
                    "raw_content_sha256": lineage.raw_content_sha256,
                    "adjustment_basis": lineage.adjustment_basis,
                    "use_case": lineage.use_case.value,
                    "validation": {
                        "status": outcomes[lineage.dataset_id].status.value,
                        "policy_version": outcomes[lineage.dataset_id].policy_version,
                        "issue_codes": sorted(issue.code for issue in outcomes[lineage.dataset_id].issues),
                    },
                }
                for lineage in sorted(manifest.lineages, key=lambda item: item.dataset_id)
            ],
            "execution_assumptions": {
                "initial_cash": manifest.execution_assumptions.initial_cash,
                "quantity": manifest.execution_assumptions.quantity,
                "commission_bps": manifest.execution_assumptions.commission_bps,
                "slippage_bps": manifest.execution_assumptions.slippage_bps,
                "force_close_at_end": manifest.execution_assumptions.force_close_at_end,
                "execution_timing": manifest.execution_assumptions.execution_timing,
            },
        }

    @staticmethod
    def _result_payload(result) -> dict[str, Any] | None:
        if result is None:
            return None
        return {
            "instrument_id": result.instrument_id,
            "dataset_id": result.dataset_id,
            "result_spec_id": result.backtest.spec.spec_id,
            "artifact_trade_count": len(result.backtest.trades),
            "artifact_equity_point_count": len(result.backtest.equity_curve),
        }

    @staticmethod
    def _paper_payload(evidence: PaperRunEligibilityEvidence | None) -> dict[str, Any] | None:
        if evidence is None:
            return None
        return {
            "evidence_id": evidence.evidence_id,
            "state": evidence.state.value,
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
        }

    @staticmethod
    def _robustness_payload(evidence: RobustnessEvidence | None) -> dict[str, Any] | None:
        if evidence is None:
            return None
        return {
            "evidence_id": evidence.evidence_id,
            "dataset_id": evidence.dataset_id,
            "strategy_id": evidence.strategy_id,
            "strategy_version": evidence.strategy_version,
            "policy_version": evidence.split_policy.policy_version,
            "in_sample_ratio": evidence.split_policy.in_sample_ratio,
            "embargo_bars": evidence.split_policy.embargo_bars,
            "max_grid_cells": evidence.split_policy.max_grid_cells,
            "gate_state": evidence.gate_state.value,
            "in_sample_end": evidence.in_sample_end.isoformat(),
            "holdout_start": evidence.holdout_start.isoformat(),
            "candidate_statuses": [
                {"parameter_revision_id": item.parameter_revision_id, "status": item.status}
                for item in evidence.candidates
            ],
            "created_at": evidence.created_at.isoformat(),
            "selection_bias_warning": evidence.selection_bias_warning,
        }

    @staticmethod
    def _review_payload(evidence: DatasetReviewEvidence | None) -> dict[str, Any] | None:
        if evidence is None:
            return None
        return {
            "evidence_id": evidence.evidence_id,
            "state": evidence.state.value,
            "dataset_id": evidence.dataset_id,
            "instrument_id": evidence.instrument_id,
            "interval": evidence.interval,
            "provenance_raw_content_sha256": evidence.provenance_raw_content_sha256,
            "adjustment_basis": evidence.adjustment_basis,
            "policy_version": evidence.policy_version,
            "blocking_reasons": list(evidence.blocking_reasons),
            "evaluated_at": evidence.evaluated_at.isoformat(),
        }

    @staticmethod
    def _verified(payload: dict[str, Any]) -> RetainedEvidenceManifest:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        digest = sha256(canonical.encode("utf-8")).hexdigest()
        verified_payload = {
            **payload,
            "verification": {
                "algorithm": "sha256",
                "canonicalization": "utf-8 JSON, sort_keys=true, separators=(',', ':'), verification excluded",
                "sha256": digest,
            },
        }
        return RetainedEvidenceManifest(
            payload=verified_payload,
            canonical_json=canonical,
            manifest_sha256=digest,
        )
