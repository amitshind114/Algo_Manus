"""Option Q acceptance tests for read-only deterministic retained-manifest comparison."""

from __future__ import annotations

from hashlib import sha256
import json
import unittest

from algo_manus.application.retained_evidence_manifest import RetainedEvidenceManifest
from algo_manus.application.retained_manifest_comparison import (
    ManifestDifferenceCategory,
    LocalRetainedManifestComparisonService,
)


def _manifest(payload: dict) -> RetainedEvidenceManifest:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = sha256(canonical.encode("utf-8")).hexdigest()
    return RetainedEvidenceManifest(
        payload={**payload, "verification": {"algorithm": "sha256", "sha256": digest}},
        canonical_json=canonical,
        manifest_sha256=digest,
    )


def _payload(*, marker: str = "left") -> dict:
    return {
        "schema": "algo-manus.retained-evidence-manifest",
        "schema_version": 1,
        "selection": {"batch_id": f"EXP-{marker}", "instrument_id": "FIXTURE:ALPHA", "paper_run_evidence_id": f"PEG-{marker}"},
        "experiment": {
            "batch_id": f"EXP-{marker}",
            "created_at": "2026-08-26T10:00:00+00:00",
            "strategy_id": "sma_crossover",
            "parameter_revision_id": "PARAM-left",
        },
        "research_manifest": {
            "manifest_id": f"RUN-{marker}",
            "parameter_revision_id": "PARAM-left",
            "information_cutoff": "2026-07-15T09:15:00+00:00",
            "lineages": [
                {
                    "dataset_id": f"DATA-{marker}",
                    "instrument_id": "FIXTURE:ALPHA",
                    "interval": "1d",
                    "raw_content_sha256": f"sha-{marker}",
                    "adjustment_basis": "declared basis",
                    "source_uri": "local://must-not-compare/source-uri",
                }
            ],
            "execution_assumptions": {"commission_bps": 10, "slippage_bps": 5, "execution_timing": "next_bar_open"},
        },
        "selected_evidence": {
            "paper_run": {"evidence_id": f"PEG-{marker}", "policy_version": "paper-v1", "evaluated_at": "2026-08-26T10:00:00+00:00", "blocking_reasons": ["REASON-left"]},
            "robustness": {"evidence_id": f"ROB-{marker}", "policy_version": "split-v1", "created_at": "2026-08-26T09:15:00+00:00"},
            "dataset_review": {"evidence_id": f"DREV-{marker}", "policy_version": "review-v1", "evaluated_at": "2026-08-26T10:00:00+00:00", "blocking_reasons": []},
            "linkage": {"state": "LINKED_REVIEW_COMPLETE", "conditions": []},
        },
        "conditions": ["REASON-left"],
        "secret_exclusion": {"manual_reference_contents_excluded": True},
    }


class RetainedManifestComparisonTests(unittest.TestCase):
    def test_identical_manifests_compare_equal_without_action_capability(self) -> None:
        left = _manifest(_payload())
        result = LocalRetainedManifestComparisonService().compare(left=left, right=left)

        self.assertTrue(result.equivalent)
        self.assertEqual(result.differences, ())
        self.assertFalse(hasattr(result, "approve"))
        self.assertFalse(hasattr(LocalRetainedManifestComparisonService, "merge"))

    def test_comparison_reports_ordered_safe_hash_lineage_policy_parameter_timestamp_and_blocker_differences(self) -> None:
        left_payload = _payload(marker="left")
        right_payload = _payload(marker="right")
        right_payload["experiment"]["created_at"] = "2026-08-27T10:00:00+00:00"
        right_payload["experiment"]["parameter_revision_id"] = "PARAM-right"
        right_payload["research_manifest"]["parameter_revision_id"] = "PARAM-right"
        right_payload["research_manifest"]["execution_assumptions"]["commission_bps"] = 15
        right_payload["selected_evidence"]["paper_run"]["policy_version"] = "paper-v2"
        right_payload["selected_evidence"]["paper_run"]["blocking_reasons"] = ["REASON-right"]
        right_payload["conditions"] = ["REASON-right"]
        left = _manifest(left_payload)
        right = _manifest(right_payload)

        result = LocalRetainedManifestComparisonService().compare(left=left, right=right)
        categories = {item.category for item in result.differences}

        self.assertFalse(result.equivalent)
        self.assertIn(ManifestDifferenceCategory.HASH, categories)
        self.assertIn(ManifestDifferenceCategory.LINEAGE, categories)
        self.assertIn(ManifestDifferenceCategory.POLICY, categories)
        self.assertIn(ManifestDifferenceCategory.PARAMETER, categories)
        self.assertIn(ManifestDifferenceCategory.TIMESTAMP, categories)
        self.assertIn(ManifestDifferenceCategory.BLOCKER, categories)
        self.assertEqual(list(result.differences), sorted(result.differences, key=lambda item: (item.category.value, item.path)))
        self.assertNotIn("must-not-compare", json.dumps(result.rows(), default=str))


if __name__ == "__main__":
    unittest.main()
