"""Read-only deterministic comparison of two retained evidence manifests.

The comparison is an in-memory inspection over the export-safe values already
present in two ``RetainedEvidenceManifest`` instances.  It does not persist a
comparison, rebuild research, select a manifest, assess quality, merge records,
authorize paper activity, or interact with data providers or execution systems.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from algo_manus.application.retained_evidence_manifest import RetainedEvidenceManifest


class ManifestDifferenceCategory(str, Enum):
    """Named, descriptive categories for retained-manifest value differences."""

    BLOCKER = "blocker"
    HASH = "hash"
    LINEAGE = "lineage"
    PARAMETER = "parameter"
    POLICY = "policy"
    TIMESTAMP = "timestamp"


@dataclass(frozen=True, slots=True)
class ManifestDifference:
    """One value-level difference over an explicit export-safe manifest path."""

    category: ManifestDifferenceCategory
    path: str
    left_value: Any
    right_value: Any


@dataclass(frozen=True, slots=True)
class RetainedEvidenceManifestComparison:
    """In-memory identity/difference report; it is never a decision or approval record."""

    left_manifest_sha256: str
    right_manifest_sha256: str
    equivalent: bool
    differences: tuple[ManifestDifference, ...]

    def rows(self) -> tuple[dict[str, Any], ...]:
        """Return display-safe, serializable difference rows in deterministic order."""

        return tuple(
            {
                "category": difference.category.value,
                "path": difference.path,
                "left_value": difference.left_value,
                "right_value": difference.right_value,
            }
            for difference in self.differences
        )


class LocalRetainedManifestComparisonService:
    """Compare two retained manifests using an allowlist of already export-safe values."""

    _MISSING = object()

    def compare(
        self,
        *,
        left: RetainedEvidenceManifest,
        right: RetainedEvidenceManifest,
    ) -> RetainedEvidenceManifestComparison:
        """Return a deterministic, descriptive comparison without mutating either manifest."""

        differences: list[ManifestDifference] = []
        self._compare_values(
            path="",
            left=self._safe_payload(left.payload),
            right=self._safe_payload(right.payload),
            differences=differences,
        )
        if left.manifest_sha256 != right.manifest_sha256:
            differences.append(
                ManifestDifference(
                    category=ManifestDifferenceCategory.HASH,
                    path="verification.sha256",
                    left_value=left.manifest_sha256,
                    right_value=right.manifest_sha256,
                )
            )
        ordered = tuple(sorted(differences, key=lambda item: (item.category.value, item.path)))
        return RetainedEvidenceManifestComparison(
            left_manifest_sha256=left.manifest_sha256,
            right_manifest_sha256=right.manifest_sha256,
            equivalent=not ordered,
            differences=ordered,
        )

    @classmethod
    def _safe_payload(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Return only fields intentionally included in the Option P export contract.

        This defensive allowlist means a manually inserted source URI, review
        note, reference text, credential, token, detailed trade, or equity point
        cannot become comparison output even if it is present on an invalid input.
        """

        selection = cls._mapping(payload.get("selection"))
        experiment = cls._mapping(payload.get("experiment"))
        manifest = cls._mapping(payload.get("research_manifest"))
        selected = cls._mapping(payload.get("selected_evidence"))
        return {
            "schema": payload.get("schema"),
            "schema_version": payload.get("schema_version"),
            "export_scope": payload.get("export_scope"),
            "fixture_or_local_research_only": payload.get("fixture_or_local_research_only"),
            "not_market_broker_or_execution_evidence": payload.get("not_market_broker_or_execution_evidence"),
            "selection": cls._pick(selection, "batch_id", "instrument_id", "paper_run_evidence_id"),
            "experiment": cls._pick(
                experiment,
                "batch_id",
                "created_at",
                "status",
                "universe_id",
                "universe_snapshot_id",
                "strategy_id",
                "parameter_revision_id",
                "research_manifest_id",
            ) if experiment else None,
            "research_manifest": cls._safe_research_manifest(manifest) if manifest else None,
            "selected_evidence": {
                "result": cls._safe_result(cls._mapping(selected.get("result"))),
                "paper_run": cls._safe_paper(cls._mapping(selected.get("paper_run"))),
                "robustness": cls._safe_robustness(cls._mapping(selected.get("robustness"))),
                "dataset_review": cls._safe_review(cls._mapping(selected.get("dataset_review"))),
                "linkage": cls._safe_linkage(cls._mapping(selected.get("linkage"))),
            },
            "conditions": cls._safe_strings(payload.get("conditions")),
            "secret_exclusion": cls._pick(
                cls._mapping(payload.get("secret_exclusion")),
                "manual_reference_contents_excluded",
                "review_notes_excluded",
                "source_uris_excluded",
                "credentials_and_tokens_excluded",
                "detailed_trades_and_equity_excluded",
            ),
        }

    @classmethod
    def _safe_research_manifest(cls, manifest: Mapping[str, Any]) -> dict[str, Any]:
        return {
            **cls._pick(
                manifest,
                "manifest_id",
                "strategy_id",
                "strategy_version",
                "parameter_revision_id",
                "engine_version",
                "start",
                "end",
                "information_cutoff",
            ),
            "lineages": [
                {
                    **cls._pick(
                        cls._mapping(lineage),
                        "dataset_id",
                        "instrument_id",
                        "interval",
                        "source_name",
                        "source_kind",
                        "retrieved_at",
                        "raw_content_sha256",
                        "adjustment_basis",
                        "use_case",
                    ),
                    "validation": cls._pick(
                        cls._mapping(cls._mapping(lineage).get("validation")),
                        "status",
                        "policy_version",
                        "issue_codes",
                    ),
                }
                for lineage in cls._safe_mappings(manifest.get("lineages"))
            ],
            "execution_assumptions": cls._pick(
                cls._mapping(manifest.get("execution_assumptions")),
                "initial_cash",
                "quantity",
                "commission_bps",
                "slippage_bps",
                "force_close_at_end",
                "execution_timing",
            ),
        }

    @classmethod
    def _safe_result(cls, result: Mapping[str, Any]) -> dict[str, Any] | None:
        return cls._pick(result, "instrument_id", "dataset_id", "result_spec_id", "artifact_trade_count", "artifact_equity_point_count") if result else None

    @classmethod
    def _safe_paper(cls, paper: Mapping[str, Any]) -> dict[str, Any] | None:
        return cls._pick(
            paper,
            "evidence_id",
            "state",
            "manifest_id",
            "dataset_id",
            "strategy_id",
            "strategy_version",
            "parameter_revision_id",
            "robustness_evidence_id",
            "policy_version",
            "central_policy_version",
            "kill_switch_change_id",
            "blocking_reasons",
            "evaluated_at",
        ) if paper else None

    @classmethod
    def _safe_robustness(cls, robustness: Mapping[str, Any]) -> dict[str, Any] | None:
        return {
            **cls._pick(
                robustness,
                "evidence_id",
                "dataset_id",
                "strategy_id",
                "strategy_version",
                "policy_version",
                "in_sample_ratio",
                "embargo_bars",
                "max_grid_cells",
                "gate_state",
                "in_sample_end",
                "holdout_start",
                "created_at",
                "selection_bias_warning",
            ),
            "candidate_statuses": [
                cls._pick(candidate, "parameter_revision_id", "status")
                for candidate in cls._safe_mappings(robustness.get("candidate_statuses"))
            ],
        } if robustness else None

    @classmethod
    def _safe_review(cls, review: Mapping[str, Any]) -> dict[str, Any] | None:
        return cls._pick(
            review,
            "evidence_id",
            "state",
            "dataset_id",
            "instrument_id",
            "interval",
            "provenance_raw_content_sha256",
            "adjustment_basis",
            "policy_version",
            "blocking_reasons",
            "evaluated_at",
        ) if review else None

    @classmethod
    def _safe_linkage(cls, linkage: Mapping[str, Any]) -> dict[str, Any] | None:
        return cls._pick(linkage, "state", "dataset_review_evidence_id", "conditions") if linkage else None

    @classmethod
    def _compare_values(
        cls,
        *,
        path: str,
        left: Any,
        right: Any,
        differences: list[ManifestDifference],
    ) -> None:
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            for key in sorted(set(left) | set(right)):
                child_path = f"{path}.{key}" if path else str(key)
                cls._compare_values(
                    path=child_path,
                    left=left.get(key, cls._MISSING),
                    right=right.get(key, cls._MISSING),
                    differences=differences,
                )
            return
        if isinstance(left, list) and isinstance(right, list):
            for index in range(max(len(left), len(right))):
                child_path = f"{path}[{index}]"
                cls._compare_values(
                    path=child_path,
                    left=left[index] if index < len(left) else cls._MISSING,
                    right=right[index] if index < len(right) else cls._MISSING,
                    differences=differences,
                )
            return
        if left != right:
            differences.append(
                ManifestDifference(
                    category=cls._category_for(path),
                    path=path,
                    left_value=None if left is cls._MISSING else left,
                    right_value=None if right is cls._MISSING else right,
                )
            )

    @staticmethod
    def _category_for(path: str) -> ManifestDifferenceCategory:
        lowered = path.lower()
        if "blocking_reasons" in lowered or lowered == "conditions" or ".conditions[" in lowered:
            return ManifestDifferenceCategory.BLOCKER
        if any(token in lowered for token in ("created_at", "evaluated_at", "retrieved_at", "information_cutoff", "in_sample_end", "holdout_start", ".start", ".end")):
            return ManifestDifferenceCategory.TIMESTAMP
        if "parameter_revision" in lowered or "candidate_statuses" in lowered:
            return ManifestDifferenceCategory.PARAMETER
        if any(
            token in lowered
            for token in (
                "policy",
                "execution_assumptions",
                "commission_bps",
                "slippage_bps",
                "initial_cash",
                "quantity",
                "embargo_bars",
                "in_sample_ratio",
                "max_grid_cells",
                "force_close_at_end",
                "execution_timing",
            )
        ):
            return ManifestDifferenceCategory.POLICY
        return ManifestDifferenceCategory.LINEAGE

    @classmethod
    def _pick(cls, source: Mapping[str, Any], *keys: str) -> dict[str, Any]:
        return {key: source.get(key) for key in keys}

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _safe_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
        return tuple(item for item in value if isinstance(item, Mapping)) if isinstance(value, list) else ()

    @staticmethod
    def _safe_strings(value: Any) -> list[str]:
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
