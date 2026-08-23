"""Read-only aggregate health coverage for local fixture evidence artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LocalEvidenceHealth:
    total_result_count: int
    complete_count: int
    unavailable_count: int
    incomplete_count: int
    result_spec_mismatch_count: int

    def __post_init__(self) -> None:
        counts = (
            self.total_result_count,
            self.complete_count,
            self.unavailable_count,
            self.incomplete_count,
            self.result_spec_mismatch_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("local evidence-health counts cannot be negative")
        if self.total_result_count != sum(counts[1:]):
            raise ValueError("local evidence-health status counts must equal total results")

    @property
    def non_complete_count(self) -> int:
        return self.total_result_count - self.complete_count


class LocalEvidenceHealthRepository(Protocol):
    def evidence_health_snapshot(self) -> LocalEvidenceHealth: ...


class LocalEvidenceHealthReadService:
    """Read aggregate local integrity status only; it has no remediation authority."""

    def __init__(self, repository: LocalEvidenceHealthRepository) -> None:
        self._repository = repository

    def snapshot(self) -> LocalEvidenceHealth:
        return self._repository.evidence_health_snapshot()
