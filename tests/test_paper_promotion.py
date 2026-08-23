from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.demo_workbench import FixtureWorkbenchService


class PaperPromotionTests(unittest.TestCase):
    def test_persisted_fixture_batch_resolves_exact_manifest_and_validation(self) -> None:
        with TemporaryDirectory() as directory:
            service = FixtureWorkbenchService(Path(directory))
            batch = service.run_experiment(
                selected_instrument_ids=("FIXTURE:NSE:EQ:ALPHA",),
                fast_window=3,
                slow_window=5,
                initial_cash=100_000,
                quantity=10,
                commission_bps=1.0,
                slippage_bps=1.0,
            )
            resolved = service.paper_promotion(batch_id=batch.batch_id, instrument_id="FIXTURE:NSE:EQ:ALPHA")

            self.assertIsNotNone(resolved)
            evidence, outcome = resolved
            self.assertEqual(evidence.manifest_id, batch.research_manifest_id)
            self.assertEqual(evidence.dataset_id, outcome.dataset_id)
            self.assertEqual(evidence.validation_policy_version, outcome.policy_version)

    def test_unknown_or_wrong_instrument_cannot_be_promoted(self) -> None:
        with TemporaryDirectory() as directory:
            service = FixtureWorkbenchService(Path(directory))
            self.assertIsNone(service.paper_promotion(batch_id="unknown", instrument_id="FIXTURE:NSE:EQ:ALPHA"))
