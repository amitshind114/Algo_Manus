"""Chronological read-only aggregation of retained local evidence-health detail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from algo_manus.application.evidence_health_detail import LocalEvidenceHealthDetailRepository


@dataclass(frozen=True, slots=True)
class LocalEvidenceHealthHistoryRow:
    batch_id: str
    created_at: datetime
    total_result_count: int
    complete_count: int
    unavailable_count: int
    incomplete_count: int
    result_spec_mismatch_count: int

    def __post_init__(self) -> None:
        if not self.batch_id:
            raise ValueError("local health-history batch id is required")
        if self.created_at.tzinfo is None:
            raise ValueError("local health-history creation time must be timezone-aware")
        counts = (
            self.total_result_count,
            self.complete_count,
            self.unavailable_count,
            self.incomplete_count,
            self.result_spec_mismatch_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("local health-history counts cannot be negative")
        if self.total_result_count != sum(counts[1:]):
            raise ValueError("local health-history status counts must equal total results")

    @property
    def non_complete_count(self) -> int:
        return self.total_result_count - self.complete_count


class LocalEvidenceHealthHistoryReadService:
    """Group read-only local detail rows by retained batch creation time."""

    def __init__(self, repository: LocalEvidenceHealthDetailRepository) -> None:
        self._repository = repository

    def list(self) -> tuple[LocalEvidenceHealthHistoryRow, ...]:
        groups: dict[str, list] = {}
        for detail in self._repository.evidence_health_details():
            groups.setdefault(detail.batch_id, []).append(detail)
        rows = []
        for batch_id, details in groups.items():
            statuses = [detail.status.value for detail in details]
            rows.append(
                LocalEvidenceHealthHistoryRow(
                    batch_id=batch_id,
                    created_at=details[0].created_at,
                    total_result_count=len(details),
                    complete_count=statuses.count("complete"),
                    unavailable_count=statuses.count("unavailable"),
                    incomplete_count=statuses.count("incomplete"),
                    result_spec_mismatch_count=statuses.count("result_spec_mismatch"),
                )
            )
        return tuple(sorted(rows, key=lambda item: (item.created_at, item.batch_id)))
