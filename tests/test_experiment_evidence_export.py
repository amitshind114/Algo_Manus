import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService
from algo_manus.application.experiment_export import EvidenceExportRefusedError


class ExperimentEvidenceExportTests(unittest.TestCase):
    def test_complete_persisted_batch_exports_summary_and_detail_after_restart(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            batch = FixtureWorkbenchService(root).run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA", "FIXTURE:NSE:EQ:CEDAR"),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )

            export = FixtureWorkbenchService(root).evidence_export(batch_id=batch.batch_id)
            summary = json.loads(export.summary_json())
            detail = json.loads(export.detailed_json())

            self.assertEqual(summary["batch_id"], batch.batch_id)
            self.assertEqual(summary["research_manifest_id"], batch.research_manifest_id)
            self.assertEqual(len(summary["results"]), 2)
            self.assertTrue(summary["detailed_export_allowed"])
            self.assertEqual(detail["batch_id"], batch.batch_id)
            self.assertEqual({item["instrument_id"] for item in detail["results"]}, {"FIXTURE:NSE:EQ:ALPHA", "FIXTURE:NSE:EQ:CEDAR"})
            self.assertTrue(all("equity_curve" in item and "trades" in item for item in detail["results"]))

    def test_incomplete_or_mismatched_detail_is_refused_but_summary_remains_available(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            batch = FixtureWorkbenchService(root).run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            with sqlite3.connect(root / "experiments.sqlite3") as connection:
                connection.execute(
                    "UPDATE experiment_result_artifacts SET result_spec_id = 'BT-mismatch' WHERE batch_id = ?",
                    (batch.batch_id,),
                )

            export = FixtureWorkbenchService(root).evidence_export(batch_id=batch.batch_id)
            summary = json.loads(export.summary_json())

            self.assertFalse(summary["detailed_export_allowed"])
            self.assertEqual(summary["results"][0]["artifact_integrity"], "result_spec_mismatch")
            with self.assertRaises(EvidenceExportRefusedError):
                export.detailed_json()

    def test_verification_metadata_is_stable_for_identical_persisted_evidence(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            batch = FixtureWorkbenchService(root).run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )

            first = FixtureWorkbenchService(root).evidence_export(batch_id=batch.batch_id)
            second = FixtureWorkbenchService(root).evidence_export(batch_id=batch.batch_id)
            first_summary = json.loads(first.summary_json())
            second_summary = json.loads(second.summary_json())
            first_detail = json.loads(first.detailed_json())
            second_detail = json.loads(second.detailed_json())

            self.assertEqual(first_summary["schema"], "algo-manus.local-evidence-summary")
            self.assertEqual(first_summary["schema_version"], 1)
            self.assertEqual(first_summary["verification"], second_summary["verification"])
            self.assertEqual(first_detail["verification"], second_detail["verification"])
            self.assertTrue(first_summary["verification"]["sha256"])
            self.assertTrue(first_detail["verification"]["sha256"])

    def test_verification_hash_changes_when_exported_detail_changes_without_external_service(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            batch = FixtureWorkbenchService(root).run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=6,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            before = json.loads(
                FixtureWorkbenchService(root).evidence_export(batch_id=batch.batch_id).detailed_json()
            )
            with sqlite3.connect(root / "experiments.sqlite3") as connection:
                connection.execute(
                    "UPDATE experiment_equity_points SET equity = equity + 1 WHERE batch_id = ? AND sequence = 0",
                    (batch.batch_id,),
                )

            after = json.loads(
                FixtureWorkbenchService(root).evidence_export(batch_id=batch.batch_id).detailed_json()
            )

            self.assertNotEqual(before["verification"]["sha256"], after["verification"]["sha256"])
