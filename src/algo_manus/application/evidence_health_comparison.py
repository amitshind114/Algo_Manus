"""Read-only side-by-side comparison of two retained local evidence-health scopes."""

from __future__ import annotations

from dataclasses import dataclass

from algo_manus.application.evidence_health_detail import LocalEvidenceHealthDetailRepository
from algo_manus.application.evidence_health_scope import (
    LocalEvidenceHealthScope,
    LocalEvidenceHealthScopeReadService,
)


@dataclass(frozen=True, slots=True)
class LocalEvidenceHealthCountDelta:
    """Right scope count minus left scope count; values may be negative."""

    total_result_count: int
    complete_count: int
    unavailable_count: int
    incomplete_count: int
    result_spec_mismatch_count: int
    non_complete_count: int


@dataclass(frozen=True, slots=True)
class LocalEvidenceHealthComparison:
    left: LocalEvidenceHealthScope
    right: LocalEvidenceHealthScope
    delta: LocalEvidenceHealthCountDelta


class LocalEvidenceHealthComparisonReadService:
    """Compare retained local batch scopes only; no record or workflow can be changed."""

    def __init__(self, repository: LocalEvidenceHealthDetailRepository) -> None:
        self._scope_reader = LocalEvidenceHealthScopeReadService(repository)

    def compare(
        self,
        *,
        left_batch_id: str,
        right_batch_id: str,
    ) -> LocalEvidenceHealthComparison:
        if not left_batch_id or not right_batch_id:
            raise ValueError("both retained local batch identifiers are required for comparison")
        if left_batch_id == right_batch_id:
            raise ValueError("two distinct retained local batches are required for comparison")
        left = self._scope_reader.read(batch_id=left_batch_id)
        right = self._scope_reader.read(batch_id=right_batch_id)
        return LocalEvidenceHealthComparison(
            left=left,
            right=right,
            delta=LocalEvidenceHealthCountDelta(
                total_result_count=right.health.total_result_count - left.health.total_result_count,
                complete_count=right.health.complete_count - left.health.complete_count,
                unavailable_count=right.health.unavailable_count - left.health.unavailable_count,
                incomplete_count=right.health.incomplete_count - left.health.incomplete_count,
                result_spec_mismatch_count=(
                    right.health.result_spec_mismatch_count - left.health.result_spec_mismatch_count
                ),
                non_complete_count=right.health.non_complete_count - left.health.non_complete_count,
            ),
        )
