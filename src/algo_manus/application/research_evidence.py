"""Local read use case for persisted, immutable research evidence."""

from __future__ import annotations

from algo_manus.domain.research import ResearchRunManifest, ResearchRunManifestRepository


class ResearchEvidenceReadService:
    """Returns persisted manifests for future UI/query composition without mutation."""

    def __init__(self, repository: ResearchRunManifestRepository) -> None:
        self._repository = repository

    def get_manifest(self, manifest_id: str) -> ResearchRunManifest | None:
        return self._repository.get(manifest_id)

    def recent_manifests(self, limit: int = 20) -> tuple[ResearchRunManifest, ...]:
        return self._repository.list_recent(limit)
