"""Read-only lifecycle visibility for local fixture experiment evidence stores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LocalEvidenceLifecycle:
    is_persistent: bool
    database_path: str | None
    database_size_bytes: int
    batch_count: int
    result_count: int
    artifact_count: int
    completed_trade_count: int
    equity_point_count: int
    oldest_batch_created_at: datetime | None
    newest_batch_created_at: datetime | None
    max_equity_points_per_result: int | None
    max_trades_per_result: int | None

    def __post_init__(self) -> None:
        values = (
            self.database_size_bytes,
            self.batch_count,
            self.result_count,
            self.artifact_count,
            self.completed_trade_count,
            self.equity_point_count,
        )
        if any(value < 0 for value in values):
            raise ValueError("local lifecycle counts cannot be negative")
        for value in (self.max_equity_points_per_result, self.max_trades_per_result):
            if value is not None and value <= 0:
                raise ValueError("local lifecycle retention limits must be positive when present")
        for value in (self.oldest_batch_created_at, self.newest_batch_created_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("local lifecycle timestamps must be timezone-aware")


class LocalEvidenceLifecycleRepository(Protocol):
    def lifecycle_snapshot(self) -> LocalEvidenceLifecycle: ...


class LocalEvidenceLifecycleReadService:
    """Return store metadata only; it has no deletion, compaction or repair authority."""

    def __init__(self, repository: LocalEvidenceLifecycleRepository) -> None:
        self._repository = repository

    def snapshot(self) -> LocalEvidenceLifecycle:
        return self._repository.lifecycle_snapshot()
