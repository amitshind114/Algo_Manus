"""Typed read model joining a persisted experiment with its research evidence."""

from __future__ import annotations

from dataclasses import dataclass

from algo_manus.application.experiments import ExperimentBatchRepository
from algo_manus.domain.experiment import ExperimentBatch
from algo_manus.domain.research import ResearchRunManifest, ResearchRunManifestRepository


@dataclass(frozen=True, slots=True)
class ExperimentEvidenceView:
    """A read-only experiment batch plus the exact manifest it references."""

    batch: ExperimentBatch
    manifest: ResearchRunManifest


class ExperimentEvidenceReadService:
    """Loads cross-repository research evidence without mutating either record."""

    def __init__(
        self,
        batches: ExperimentBatchRepository,
        manifests: ResearchRunManifestRepository,
    ) -> None:
        self._batches = batches
        self._manifests = manifests

    def get(self, batch_id: str) -> ExperimentEvidenceView | None:
        batch = self._batches.get(batch_id)
        if batch is None or batch.research_manifest_id is None:
            return None
        manifest = self._manifests.get(batch.research_manifest_id)
        if manifest is None:
            raise RuntimeError("experiment references a missing research manifest")
        return ExperimentEvidenceView(batch=batch, manifest=manifest)
