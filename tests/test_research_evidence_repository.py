from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.research_evidence import ResearchEvidenceReadService
from algo_manus.domain.market_data import Candle, CandleDataset, DataProvenance, DataSourceKind, DataUseCase
from algo_manus.domain.research import (
    DataValidationIssue,
    DataValidationSeverity,
    DataValidationStatus,
    DatasetLineage,
    DatasetValidationOutcome,
    ResearchExecutionAssumptions,
    ResearchRunManifest,
)
from algo_manus.infrastructure.research import SqliteResearchEvidenceRepository


class ResearchEvidenceRepositoryTests(unittest.TestCase):
    def _manifest(self, *, created_at: datetime) -> ResearchRunManifest:
        start = datetime(2026, 8, 1, 9, 15, tzinfo=timezone.utc)
        dataset = CandleDataset.create(
            instrument_id="FIXTURE:NSE:EQ:ALPHA",
            interval="1d",
            provenance=DataProvenance(
                source_name="fixture-research",
                source_kind=DataSourceKind.FIXTURE,
                source_uri="fixture://research/repository",
                retrieved_at=start,
                raw_content_sha256=sha256(b"repository-manifest-fixture").hexdigest(),
                adjustment_basis="synthetic unadjusted bars",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=(
                Candle(timestamp=start, open=100, high=101, low=99, close=100, volume=1_000),
                Candle(timestamp=start + timedelta(days=1), open=101, high=102, low=100, close=101, volume=1_100),
            ),
        )
        outcome = DatasetValidationOutcome(
            dataset_id=dataset.dataset_id,
            status=DataValidationStatus.ACCEPTED,
            policy_version="dataset-validation-v1",
            validated_at=start + timedelta(minutes=30),
        )
        return ResearchRunManifest(
            universe_id="fixture-universe",
            universe_snapshot_id="FIXTURE-SNAPSHOT-LOCAL-V1",
            strategy_id="sma_crossover",
            strategy_version="1.0.0",
            parameter_revision_id="PARAM-repository",
            engine_version="backtest-v1",
            lineages=(DatasetLineage.from_dataset(dataset),),
            validation_outcomes=(outcome,),
            execution_assumptions=ResearchExecutionAssumptions(
                initial_cash=100_000,
                quantity=100,
                commission_bps=10,
                slippage_bps=5,
            ),
            start=start,
            end=start + timedelta(days=1),
            information_cutoff=start,
            created_at=created_at,
            git_commit_sha="3bd48b9",
        )

    def test_round_trip_is_idempotent_and_available_through_read_service(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "research_evidence.sqlite"
            manifest = self._manifest(created_at=datetime(2026, 8, 1, 11, 15, tzinfo=timezone.utc))
            repository = SqliteResearchEvidenceRepository(path)
            repository.save(manifest)
            repository.save(manifest)

            restored = repository.get(manifest.manifest_id)
            recent = ResearchEvidenceReadService(repository).recent_manifests()

            self.assertEqual(restored, manifest)
            self.assertEqual(recent, (manifest,))
            self.assertEqual(repository.get_validation(manifest.lineages[0].dataset_id, "dataset-validation-v1"), manifest.validation_outcomes[0])

    def test_conflicting_validation_is_not_silently_overwritten_and_database_closes(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "research_evidence.sqlite"
            manifest = self._manifest(created_at=datetime(2026, 8, 1, 11, 15, tzinfo=timezone.utc))
            repository = SqliteResearchEvidenceRepository(path)
            repository.save(manifest)
            conflicting = DatasetValidationOutcome(
                dataset_id=manifest.lineages[0].dataset_id,
                status=DataValidationStatus.REJECTED,
                policy_version="dataset-validation-v1",
                validated_at=datetime(2026, 8, 1, 12, 15, tzinfo=timezone.utc),
                issues=(
                    DataValidationIssue(
                        code="CONFLICT",
                        severity=DataValidationSeverity.ERROR,
                        message="same immutable validation key with conflicting content",
                    ),
                ),
            )

            with self.assertRaisesRegex(ValueError, "conflicts"):
                repository.save_validation(conflicting)
            del repository
            path.unlink()
            self.assertFalse(path.exists())

    def test_recent_read_rejects_non_positive_limit(self) -> None:
        with TemporaryDirectory() as directory:
            repository = SqliteResearchEvidenceRepository(Path(directory) / "research_evidence.sqlite")

            with self.assertRaisesRegex(ValueError, "limit"):
                ResearchEvidenceReadService(repository).recent_manifests(0)


if __name__ == "__main__":
    unittest.main()
