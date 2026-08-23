"""Read-only scope filtering for retained local evidence-health views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from algo_manus.application.evidence_health import LocalEvidenceHealth
from algo_manus.application.evidence_health_detail import (
    LocalEvidenceHealthDetail,
    LocalEvidenceHealthDetailRepository,
)
from algo_manus.application.evidence_health_history import LocalEvidenceHealthHistoryRow


@dataclass(frozen=True, slots=True)
class LocalEvidenceHealthScope:
    batch_id: str | None
    created_from: datetime | None
    created_until: datetime | None
    health: LocalEvidenceHealth
    details: tuple[LocalEvidenceHealthDetail, ...]
    history: tuple[LocalEvidenceHealthHistoryRow, ...]


class LocalEvidenceHealthScopeReadService:
    """Filter existing local health observations only; it cannot alter stored evidence."""

    def __init__(self, repository: LocalEvidenceHealthDetailRepository) -> None:
        self._repository = repository

    def read(
        self,
        *,
        batch_id: str | None = None,
        created_from: datetime | None = None,
        created_until: datetime | None = None,
    ) -> LocalEvidenceHealthScope:
        self._validate_bounds(created_from, created_until)
        all_details = self._repository.evidence_health_details()
        if batch_id is not None and batch_id not in {item.batch_id for item in all_details}:
            raise ValueError(f"unknown retained local batch: {batch_id}")
        details = tuple(
            item
            for item in all_details
            if (batch_id is None or item.batch_id == batch_id)
            and (created_from is None or item.created_at >= created_from)
            and (created_until is None or item.created_at <= created_until)
        )
        return LocalEvidenceHealthScope(
            batch_id=batch_id,
            created_from=created_from,
            created_until=created_until,
            health=self._health(details),
            details=details,
            history=self._history(details),
        )

    @staticmethod
    def _validate_bounds(created_from: datetime | None, created_until: datetime | None) -> None:
        for value in (created_from, created_until):
            if value is not None and value.tzinfo is None:
                raise ValueError("local evidence-health scope bounds must be timezone-aware")
        if created_from is not None and created_until is not None and created_from > created_until:
            raise ValueError("local evidence-health scope start cannot be after its end")

    @staticmethod
    def _health(details: tuple[LocalEvidenceHealthDetail, ...]) -> LocalEvidenceHealth:
        statuses = [item.status.value for item in details]
        return LocalEvidenceHealth(
            total_result_count=len(details),
            complete_count=statuses.count("complete"),
            unavailable_count=statuses.count("unavailable"),
            incomplete_count=statuses.count("incomplete"),
            result_spec_mismatch_count=statuses.count("result_spec_mismatch"),
        )

    @staticmethod
    def _history(
        details: tuple[LocalEvidenceHealthDetail, ...],
    ) -> tuple[LocalEvidenceHealthHistoryRow, ...]:
        groups: dict[str, list[LocalEvidenceHealthDetail]] = {}
        for detail in details:
            groups.setdefault(detail.batch_id, []).append(detail)
        rows = []
        for identifier, batch_details in groups.items():
            statuses = [item.status.value for item in batch_details]
            rows.append(
                LocalEvidenceHealthHistoryRow(
                    batch_id=identifier,
                    created_at=batch_details[0].created_at,
                    total_result_count=len(batch_details),
                    complete_count=statuses.count("complete"),
                    unavailable_count=statuses.count("unavailable"),
                    incomplete_count=statuses.count("incomplete"),
                    result_spec_mismatch_count=statuses.count("result_spec_mismatch"),
                )
            )
        return tuple(sorted(rows, key=lambda item: (item.created_at, item.batch_id)))
