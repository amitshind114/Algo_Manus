"""Bounded local robustness evaluation for retained research datasets.

This module evaluates a small declared parameter grid across chronological
in-sample and holdout partitions. It is research-only: it cannot promote a
strategy, amend a batch, call a broker, retrieve data, or create an order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from itertools import product
import json
from typing import Mapping, Protocol

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.domain.backtest import BacktestResult, BacktestSpec
from algo_manus.domain.market_data import CandleDataset
from algo_manus.domain.strategy import Strategy, StrategyParameterRevision


class RobustnessGateState(StrEnum):
    """Informational status only; no state can permit paper or live activity."""

    INFORMATIONAL_ONLY = "INFORMATIONAL_ONLY"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


@dataclass(frozen=True, slots=True)
class RobustnessSplitPolicy:
    in_sample_ratio: float
    max_grid_cells: int
    embargo_bars: int = 1
    policy_version: str = "chronological-split-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "in_sample_ratio", float(self.in_sample_ratio))
        object.__setattr__(self, "max_grid_cells", int(self.max_grid_cells))
        object.__setattr__(self, "embargo_bars", int(self.embargo_bars))
        if not 0.0 < self.in_sample_ratio < 1.0:
            raise ValueError("in_sample_ratio must be above 0 and below 1.0")
        if self.max_grid_cells <= 0 or self.max_grid_cells > 64:
            raise ValueError("max_grid_cells must be between 1 and 64")
        if self.embargo_bars <= 0:
            raise ValueError("embargo_bars must be positive")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class RobustnessGrid:
    parameter_values: Mapping[str, tuple[int | float, ...]]

    def __post_init__(self) -> None:
        normalized = {
            str(name): tuple(values)
            for name, values in self.parameter_values.items()
        }
        if not normalized:
            raise ValueError("robustness grid requires at least one parameter")
        if any(not name.strip() or not values for name, values in normalized.items()):
            raise ValueError("robustness grid names and value lists must be non-empty")
        object.__setattr__(self, "parameter_values", normalized)

    @property
    def cell_count(self) -> int:
        count = 1
        for values in self.parameter_values.values():
            count *= len(values)
        return count

    def candidates(self) -> tuple[Mapping[str, int | float], ...]:
        names = tuple(sorted(self.parameter_values))
        return tuple(
            dict(zip(names, values, strict=True))
            for values in product(*(self.parameter_values[name] for name in names))
        )


@dataclass(frozen=True, slots=True)
class RobustnessPartitionResult:
    result_spec_id: str
    net_pnl: float
    total_return_pct: float
    trade_count: int
    outcome: str
    next_bar_execution: bool = True


@dataclass(frozen=True, slots=True)
class RobustnessCandidateEvidence:
    parameters: Mapping[str, int | float]
    parameter_revision_id: str
    in_sample: RobustnessPartitionResult | None
    holdout: RobustnessPartitionResult | None
    status: str


@dataclass(frozen=True, slots=True)
class RobustnessEvidence:
    evidence_id: str
    dataset_id: str
    strategy_id: str
    strategy_version: str
    split_policy: RobustnessSplitPolicy
    in_sample_end: datetime
    holdout_start: datetime
    gate_state: RobustnessGateState
    candidates: tuple[RobustnessCandidateEvidence, ...]
    initial_cash: float
    quantity: int
    commission_bps: float
    slippage_bps: float
    force_close_at_end: bool
    selection_bias_warning: str
    created_at: datetime

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.in_sample_end.tzinfo is None or self.holdout_start.tzinfo is None:
            raise ValueError("robustness evidence timestamps must be timezone-aware")
        if self.initial_cash <= 0 or self.quantity <= 0:
            raise ValueError("robustness evidence initial_cash and quantity must be positive")
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("robustness evidence costs cannot be negative")
        if self.in_sample_end >= self.holdout_start:
            raise ValueError("in-sample data must end before holdout data begins")
        if not self.selection_bias_warning.strip():
            raise ValueError("selection_bias_warning is required")


class RobustnessEvidenceRepository(Protocol):
    def save(self, evidence: RobustnessEvidence) -> None: ...

    def get(self, evidence_id: str) -> RobustnessEvidence | None: ...

    def list_recent(self, limit: int = 20) -> tuple[RobustnessEvidence, ...]: ...


class LocalRobustnessEvaluationService:
    """Evaluate one retained dataset under a bounded grid without changing any workflow gate."""

    _WARNING = (
        "Selection bias and overfitting risk remain: a bounded grid and one chronological holdout do not establish robustness, future performance, suitability or promotion readiness."
    )

    def __init__(self, repository: RobustnessEvidenceRepository, backtester: BarBacktestService | None = None) -> None:
        self._repository = repository
        self._backtester = backtester or BarBacktestService()

    def evaluate(
        self,
        *,
        dataset: CandleDataset,
        strategy: Strategy,
        grid: RobustnessGrid,
        split_policy: RobustnessSplitPolicy,
        initial_cash: float,
        quantity: int,
        commission_bps: float,
        slippage_bps: float,
        created_at: datetime | None = None,
    ) -> RobustnessEvidence:
        if dataset.provenance.use_case.value != "RESEARCH":
            raise ValueError("robustness evaluation requires a research-use dataset")
        self._validate_grid(strategy, grid, split_policy)
        evidence_id = self._evidence_id(
            dataset=dataset,
            strategy=strategy,
            grid=grid,
            split_policy=split_policy,
            assumptions=(initial_cash, quantity, commission_bps, slippage_bps),
        )
        existing = self._repository.get(evidence_id)
        if existing is not None:
            return existing
        split_index = int(len(dataset.candles) * split_policy.in_sample_ratio)
        holdout_index = split_index + split_policy.embargo_bars
        if split_index <= 0 or holdout_index >= len(dataset.candles):
            raise ValueError("chronological split must produce in-sample and holdout bars")
        in_sample_dataset = self._partition(dataset, dataset.candles[:split_index], "in-sample")
        holdout_dataset = self._partition(dataset, dataset.candles[holdout_index:], "holdout")
        candidates = tuple(
            self._candidate(
                in_sample_dataset=in_sample_dataset,
                holdout_dataset=holdout_dataset,
                strategy=strategy,
                parameters=parameters,
                initial_cash=initial_cash,
                quantity=quantity,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
            )
            for parameters in grid.candidates()
        )
        gate_state = (
            RobustnessGateState.INSUFFICIENT_HISTORY
            if all(item.in_sample is None or item.holdout is None for item in candidates)
            else RobustnessGateState.INFORMATIONAL_ONLY
        )
        timestamp = created_at or datetime.now(timezone.utc)
        evidence = RobustnessEvidence(
            evidence_id=evidence_id,
            dataset_id=dataset.dataset_id,
            strategy_id=strategy.strategy_id,
            strategy_version=strategy.metadata.version,
            split_policy=split_policy,
            in_sample_end=in_sample_dataset.candles[-1].timestamp,
            holdout_start=holdout_dataset.candles[0].timestamp,
            gate_state=gate_state,
            candidates=candidates,
            initial_cash=float(initial_cash),
            quantity=int(quantity),
            commission_bps=float(commission_bps),
            slippage_bps=float(slippage_bps),
            force_close_at_end=True,
            selection_bias_warning=self._WARNING,
            created_at=timestamp,
        )
        self._repository.save(evidence)
        return evidence

    @staticmethod
    def _validate_grid(strategy: Strategy, grid: RobustnessGrid, policy: RobustnessSplitPolicy) -> None:
        known = {definition.name for definition in strategy.metadata.parameter_schema.definitions}
        unknown = set(grid.parameter_values) - known
        if unknown:
            raise ValueError(f"robustness grid contains unknown parameter(s): {sorted(unknown)}")
        if grid.cell_count > policy.max_grid_cells:
            raise ValueError(f"robustness grid cell count {grid.cell_count} exceeds policy limit {policy.max_grid_cells}")
        defaults = dict(strategy.metadata.parameter_schema.defaults())
        for values in grid.candidates():
            try:
                strategy.metadata.parameter_schema.validate({**defaults, **values})
            except ValueError as exc:
                raise ValueError(f"invalid robustness grid candidate: {exc}") from exc

    @staticmethod
    def _partition(dataset: CandleDataset, candles, label: str) -> CandleDataset:
        provenance = dataset.provenance
        partition_provenance = type(provenance)(
            source_name=provenance.source_name,
            source_kind=provenance.source_kind,
            source_uri=f"{provenance.source_uri}#{label}",
            retrieved_at=provenance.retrieved_at,
            raw_content_sha256=sha256(
                f"{provenance.raw_content_sha256}:{label}:{candles[0].timestamp.isoformat()}:{candles[-1].timestamp.isoformat()}".encode()
            ).hexdigest(),
            adjustment_basis=provenance.adjustment_basis,
            use_case=provenance.use_case,
        )
        return CandleDataset.create(
            instrument_id=dataset.instrument_id,
            interval=dataset.interval,
            provenance=partition_provenance,
            candles=tuple(candles),
        )

    def _candidate(
        self,
        *,
        in_sample_dataset: CandleDataset,
        holdout_dataset: CandleDataset,
        strategy: Strategy,
        parameters: Mapping[str, int | float],
        initial_cash: float,
        quantity: int,
        commission_bps: float,
        slippage_bps: float,
    ) -> RobustnessCandidateEvidence:
        revision = StrategyParameterRevision.create(strategy.strategy_id, parameters)
        in_sample = self._run_partition(
            in_sample_dataset, strategy, revision, initial_cash, quantity, commission_bps, slippage_bps
        )
        holdout = self._run_partition(
            holdout_dataset, strategy, revision, initial_cash, quantity, commission_bps, slippage_bps
        )
        status = "CALCULATED" if in_sample is not None and holdout is not None else "INSUFFICIENT_HISTORY"
        return RobustnessCandidateEvidence(
            parameters=dict(parameters),
            parameter_revision_id=revision.revision_id,
            in_sample=in_sample,
            holdout=holdout,
            status=status,
        )

    def _run_partition(
        self,
        dataset: CandleDataset,
        strategy: Strategy,
        revision: StrategyParameterRevision,
        initial_cash: float,
        quantity: int,
        commission_bps: float,
        slippage_bps: float,
    ) -> RobustnessPartitionResult | None:
        if len(dataset.candles) <= strategy.required_history(revision.parameters):
            return None
        result = self._backtester.run(
            dataset=dataset,
            strategy=strategy,
            parameters=revision,
            spec=BacktestSpec(
                dataset_id=dataset.dataset_id,
                strategy_id=strategy.strategy_id,
                parameter_revision_id=revision.revision_id,
                initial_cash=initial_cash,
                quantity=quantity,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
            ),
        )
        return self._partition_result(result)

    @staticmethod
    def _partition_result(result: BacktestResult) -> RobustnessPartitionResult:
        return RobustnessPartitionResult(
            result_spec_id=result.spec.spec_id,
            net_pnl=result.metrics.net_pnl,
            total_return_pct=result.metrics.total_return_pct,
            trade_count=result.metrics.trade_count,
            outcome=result.outcome.kind.value if result.outcome is not None else "UNAVAILABLE",
        )

    @staticmethod
    def _evidence_id(
        *,
        dataset: CandleDataset,
        strategy: Strategy,
        grid: RobustnessGrid,
        split_policy: RobustnessSplitPolicy,
        assumptions: tuple[float, int, float, float],
    ) -> str:
        canonical = json.dumps(
            {
                "dataset_id": dataset.dataset_id,
                "strategy_id": strategy.strategy_id,
                "strategy_version": strategy.metadata.version,
                "grid": {key: list(value) for key, value in sorted(grid.parameter_values.items())},
                "split_policy": {
                    "in_sample_ratio": split_policy.in_sample_ratio,
                    "max_grid_cells": split_policy.max_grid_cells,
                    "embargo_bars": split_policy.embargo_bars,
                    "policy_version": split_policy.policy_version,
                },
                "assumptions": assumptions,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"ROB-{sha256(canonical.encode()).hexdigest()[:20]}"
