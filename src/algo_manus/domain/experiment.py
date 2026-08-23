"""Immutable experiment-batch and per-security result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from algo_manus.domain.backtest import BacktestResult


class ExperimentStatus(StrEnum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    PAPER_ELIGIBLE = "PAPER_ELIGIBLE"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class SecurityExperimentResult:
    instrument_id: str
    dataset_id: str
    backtest: BacktestResult
    data_quality_note: str = "validated fixture or approved research dataset"


@dataclass(frozen=True, slots=True)
class ExperimentBatch:
    batch_id: str
    universe_id: str
    universe_snapshot_id: str
    strategy_id: str
    parameter_revision_id: str
    created_at: datetime
    status: ExperimentStatus
    results: tuple[SecurityExperimentResult, ...]
    research_manifest_id: str | None = None

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if not self.results:
            raise ValueError("an experiment batch requires at least one security result")
        if self.research_manifest_id is not None and not self.research_manifest_id.strip():
            raise ValueError("research manifest ID cannot be blank when supplied")
        if len({result.instrument_id for result in self.results}) != len(self.results):
            raise ValueError("experiment batch cannot contain duplicate instruments")
        for result in self.results:
            if result.backtest.spec.strategy_id != self.strategy_id:
                raise ValueError("all results must share the batch strategy")
            if result.backtest.spec.parameter_revision_id != self.parameter_revision_id:
                raise ValueError("all results must share the batch parameter revision")
