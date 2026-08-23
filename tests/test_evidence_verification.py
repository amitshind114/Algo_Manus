from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import json
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService
from algo_manus.application.evidence_verification import (
    EvidenceVerificationStatus,
    LocalEvidenceVerifier,
    main,
)


class LocalEvidenceVerifierTests(unittest.TestCase):
    def _summary_payload(self):
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
            return FixtureWorkbenchService(root).evidence_export(batch_id=batch.batch_id).summary_payload()

    def test_verifies_persisted_export_after_service_restart(self) -> None:
        result = LocalEvidenceVerifier().verify_payload(self._summary_payload())

        self.assertEqual(result.status, EvidenceVerificationStatus.VALID)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.schema, "algo-manus.local-evidence-summary")
        self.assertEqual(result.schema_version, 1)

    def test_detects_mutation_without_modifying_local_evidence(self) -> None:
        payload = self._summary_payload()
        mutated = deepcopy(payload)
        mutated["strategy_id"] = "changed-locally-after-export"

        result = LocalEvidenceVerifier().verify_payload(mutated)

        self.assertEqual(result.status, EvidenceVerificationStatus.MISMATCH)
        self.assertFalse(result.is_valid)

    def test_rejects_missing_verification_malformed_and_unsupported_payloads(self) -> None:
        payload = self._summary_payload()
        missing = deepcopy(payload)
        missing.pop("verification")

        verifier = LocalEvidenceVerifier()
        self.assertEqual(
            verifier.verify_payload(missing).status,
            EvidenceVerificationStatus.MISSING_VERIFICATION,
        )
        unsupported = deepcopy(payload)
        unsupported["schema"] = "unknown.local-export"
        self.assertEqual(
            verifier.verify_payload(unsupported).status,
            EvidenceVerificationStatus.UNSUPPORTED_SCHEMA,
        )
        self.assertEqual(
            verifier.verify_json("not-json").status,
            EvidenceVerificationStatus.MALFORMED,
        )
        self.assertEqual(
            verifier.verify_json(json.dumps(["not", "an", "object"])).status,
            EvidenceVerificationStatus.MALFORMED,
        )

    def test_local_command_verifies_export_file_without_uploading_it(self) -> None:
        payload = self._summary_payload()
        with TemporaryDirectory() as directory:
            export_path = Path(directory) / "fixture_evidence.json"
            export_path.write_text(json.dumps(payload), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main([str(export_path)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "valid")
