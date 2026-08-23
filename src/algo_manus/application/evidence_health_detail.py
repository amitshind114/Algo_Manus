"""Read-only per-result detail behind aggregate local evidence-health status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from algo_manus.application.experiments import ExperimentArtifactIntegrityStatus


@dataclass(frozen=True, slots=True)
class LocalEvidenceHealthDetail:
    batch_id: str
    instrument_id: str
    created_at: datetime
    status: ExperimentArtifactIntegrityStatus
    result_spec_id: str
    artifact_result_spec_id: str | None
    expected_trade_count: int | None
    actual_trade_count: int
    expected_equity_point_count: int | None
    actual_equity_point_count: int

    def __post_init__(self) -> None:
        if not self.batch_id or not self.instrument_id or not self.result_spec_id:
            raise ValueError("local evidence-health detail identifiers are required")
        if self.created_at.tzinfo is None:
            raise ValueError("local evidence-health detail creation time must be timezone-aware")
        values = (self.actual_trade_count, self.actual_equity_point_count)
        if any(value < 0 for value in values):
            raise ValueError("local evidence-health actual counts cannot be negative")
        for value in (self.expected_trade_count, self.expected_equity_point_count):
            if value is not None and value < 0:
                raise ValueError("local evidence-health expected counts cannot be negative")


class LocalEvidenceHealthDetailRepository(Protocol):
    def evidence_health_details(self) -> tuple[LocalEvidenceHealthDetail, ...]: ...


class LocalEvidenceHealthDetailReadService:
    """Expose status context only; no repair, export, deletion or workflow authority."""

    def __init__(self, repository: LocalEvidenceHealthDetailRepository) -> None:
        self._repository = repository

    def list(self) -> tuple[LocalEvidenceHealthDetail, ...]:
        return self._repository.evidence_health_details()
