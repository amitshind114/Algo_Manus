"""Option P acceptance tests for deterministic read-only retained-evidence manifests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.experiment_evidence import ExperimentEvidenceReadService
from algo_manus.application.paper_run_eligibility import (
    PaperRunEligibilityEvidence,
    PaperRunEligibilityState,
)
from algo_manus.application.retained_evidence_manifest import LocalRetainedEvidenceManifestService
from algo_manus.application.demo_workbench import FixtureWorkbenchService


class RetainedEvidenceManifestTests(unittest.TestCase):
    def _service(self, workbench: FixtureWorkbenchService) -> LocalRetainedEvidenceManifestService:
        return LocalRetainedEvidenceManifestService(
            ExperimentEvidenceReadService(workbench._batches, workbench._manifests),
            workbench._robustness,
            workbench._paper_run_eligibility,
            workbench._dataset_review,
        )

    def _batch(self, workbench: FixtureWorkbenchService):
        return workbench.run_experiment(
            selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
            fast_window=3,
            slow_window=6,
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
        )

    def test_manifest_is_canonical_restart_safe_and_excludes_manual_reference_contents(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            workbench = FixtureWorkbenchService(data_root=root)
            batch = self._batch(workbench)
            robustness = workbench.run_local_robustness_evaluation(instrument_id="FIXTURE:NSE:EQ:ALPHA")
            target = next(item for item in batch.results if item.instrument_id == "FIXTURE:NSE:EQ:ALPHA")
            workbench._paper_run_eligibility.save(
                PaperRunEligibilityEvidence(
                    evidence_id="PEG-manifest",
                    state=PaperRunEligibilityState.BLOCKED,
                    batch_id=batch.batch_id,
                    instrument_id=target.instrument_id,
                    manifest_id=batch.research_manifest_id,
                    dataset_id=target.dataset_id,
                    strategy_id=batch.strategy_id,
                    strategy_version="1.0.0",
                    parameter_revision_id=batch.parameter_revision_id,
                    robustness_evidence_id=robustness.evidence_id,
                    policy_version="paper-evidence-v1",
                    central_policy_version="central-risk-v1",
                    kill_switch_change_id="KILL-manifest",
                    blocking_reasons=("ROBUSTNESS_HISTORY_INSUFFICIENT",),
                    evaluated_at=datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc),
                )
            )
            workbench.record_dataset_review(
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
                corporate_action_source_reference="local://must-not-export/corporate-actions",
                calendar_source_reference="local://must-not-export/calendar",
                note="must-not-export manual note",
                reviewed_at=datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc),
            )
            first = self._service(workbench).build(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
            )
            restarted = FixtureWorkbenchService(data_root=root)
            second = self._service(restarted).build(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
            )

        self.assertEqual(first.canonical_json, second.canonical_json)
        self.assertEqual(first.manifest_sha256, second.manifest_sha256)
        self.assertEqual(first.payload["verification"]["sha256"], first.manifest_sha256)
        self.assertEqual(first.payload["selected_evidence"]["paper_run"]["evidence_id"], "PEG-manifest")
        self.assertIn("ROBUSTNESS_HISTORY_INSUFFICIENT", first.payload["conditions"])
        self.assertNotIn("must-not-export", first.canonical_json)
        self.assertNotIn("source_reference", first.canonical_json)
        self.assertFalse(hasattr(first, "approve"))
        self.assertFalse(hasattr(LocalRetainedEvidenceManifestService, "publish"))

    def test_missing_and_mismatched_evidence_are_named_without_substitution(self) -> None:
        with TemporaryDirectory() as directory:
            workbench = FixtureWorkbenchService(data_root=Path(directory))
            batch = self._batch(workbench)
            manifest = self._service(workbench).build(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:ALPHA",
            )
            unknown_instrument = self._service(workbench).build(
                batch_id=batch.batch_id,
                instrument_id="FIXTURE:NSE:EQ:UNKNOWN",
            )

        self.assertIn("PAPER_RUN_EVIDENCE_MISSING", manifest.payload["conditions"])
        self.assertIn("ROBUSTNESS_EVIDENCE_MISSING", manifest.payload["conditions"])
        self.assertIn("DATASET_REVIEW_EVIDENCE_MISSING", manifest.payload["conditions"])
        self.assertIn("BATCH_INSTRUMENT_EVIDENCE_MISSING", unknown_instrument.payload["conditions"])
        self.assertIsNone(unknown_instrument.payload["selected_evidence"]["result"])


if __name__ == "__main__":
    unittest.main()
