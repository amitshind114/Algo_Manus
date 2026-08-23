"""Application services for comparable multi-security research experiments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Mapping, Protocol

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.domain.backtest import BacktestResult, BacktestSpec
from algo_manus.domain.experiment import (
    ExperimentBatch,
    ExperimentStatus,
    SecurityExperimentResult,
)
from algo_manus.domain.market_data import CandleDataset, DataUseCase
from algo_manus.domain.research import (
    DataValidationStatus,
    DatasetLineage,
    DatasetValidationOutcome,
    ResearchExecutionAssumptions,
    ResearchRunManifest,
    ResearchRunManifestRepository,
)
from algo_manus.domain.strategy import Strategy, StrategyParameterRevision


class ExperimentBatchRepository(Protocol):
    def save(self, batch: ExperimentBatch) -> None: ...

    def get(self, batch_id: str) -> ExperimentBatch | None: ...


@dataclass(frozen=True, slots=True)
class BatchBacktestRequest:
    universe_id: str
    universe_snapshot_id: str
    datasets_by_instrument: Mapping[str, CandleDataset]
    initial_cash: float
    quantity: int
    commission_bps: float
    slippage_bps: float

    def __post_init__(self) -> None:
        if not self.universe_id or not self.universe_snapshot_id or not self.datasets_by_instrument:
            raise ValueError("universe metadata and at least one dataset are required")


class ExperimentBatchService:
    """Runs one strategy revision under identical assumptions across a universe."""

    _ENGINE_VERSION = "bar-backtest-v1"
    _VALIDATION_POLICY_VERSION = "research-contract-v1"

    def __init__(
        self,
        backtester: BarBacktestService,
        repository: ExperimentBatchRepository,
        manifest_repository: ResearchRunManifestRepository,
    ) -> None:
        self._backtester = backtester
        self._repository = repository
        self._manifest_repository = manifest_repository

    def run(
        self,
        *,
        request: BatchBacktestRequest,
        strategy: Strategy,
        parameters: StrategyParameterRevision,
        created_at: datetime | None = None,
    ) -> ExperimentBatch:
        datasets = tuple(request.datasets_by_instrument.values())
        first = datasets[0]
        self._validate_comparable_datasets(datasets)
        result_items: list[SecurityExperimentResult] = []
        for instrument_id, dataset in request.datasets_by_instrument.items():
            if dataset.instrument_id != instrument_id:
                raise ValueError("dataset map key must equal its instrument identity")
            spec = BacktestSpec(
                dataset_id=dataset.dataset_id,
                strategy_id=strategy.strategy_id,
                parameter_revision_id=parameters.revision_id,
                initial_cash=request.initial_cash,
                quantity=request.quantity,
                commission_bps=request.commission_bps,
                slippage_bps=request.slippage_bps,
            )
            backtest = self._backtester.run(
                dataset=dataset, strategy=strategy, parameters=parameters, spec=spec
            )
            result_items.append(
                SecurityExperimentResult(
                    instrument_id=instrument_id,
                    dataset_id=dataset.dataset_id,
                    backtest=backtest,
                )
            )
        timestamp = created_at or datetime.now(timezone.utc)
        canonical = json.dumps(
            {
                "universe_id": request.universe_id,
                "snapshot_id": request.universe_snapshot_id,
                "strategy": strategy.strategy_id,
                "parameters": parameters.revision_id,
                "datasets": sorted(dataset.dataset_id for dataset in datasets),
                "assumptions": [request.initial_cash, request.quantity, request.commission_bps, request.slippage_bps],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        manifest = self._manifest(request, strategy, parameters, datasets, timestamp)
        self._manifest_repository.save(manifest)
        batch = ExperimentBatch(
            batch_id=f"EXP-{sha256(canonical.encode()).hexdigest()[:20]}",
            universe_id=request.universe_id,
            universe_snapshot_id=request.universe_snapshot_id,
            strategy_id=strategy.strategy_id,
            parameter_revision_id=parameters.revision_id,
            created_at=timestamp,
            status=ExperimentStatus.RESEARCH_ONLY,
            results=tuple(result_items),
            research_manifest_id=manifest.manifest_id,
        )
        self._repository.save(batch)
        return batch

    @staticmethod
    def _validate_comparable_datasets(datasets: tuple[CandleDataset, ...]) -> None:
        intervals = {dataset.interval for dataset in datasets}
        adjustments = {dataset.provenance.adjustment_basis for dataset in datasets}
        if len(intervals) != 1 or len(adjustments) != 1:
            raise ValueError("all datasets in a comparable batch need the same interval and adjustment basis")
        if any(dataset.provenance.use_case is not DataUseCase.RESEARCH for dataset in datasets):
            raise ValueError("multi-security backtests require research-use datasets")

    def _manifest(
        self,
        request: BatchBacktestRequest,
        strategy: Strategy,
        parameters: StrategyParameterRevision,
        datasets: tuple[CandleDataset, ...],
        created_at: datetime,
    ) -> ResearchRunManifest:
        """Construct evidence from already-validated local research inputs only."""

        lineages = tuple(DatasetLineage.from_dataset(dataset) for dataset in datasets)
        validations = tuple(
            DatasetValidationOutcome(
                dataset_id=lineage.dataset_id,
                status=DataValidationStatus.ACCEPTED,
                policy_version=self._VALIDATION_POLICY_VERSION,
                validated_at=created_at,
            )
            for lineage in lineages
        )
        timestamps = tuple(candle.timestamp for dataset in datasets for candle in dataset.candles)
        return ResearchRunManifest(
            universe_id=request.universe_id,
            universe_snapshot_id=request.universe_snapshot_id,
            strategy_id=strategy.metadata.strategy_id,
            strategy_version=strategy.metadata.version,
            parameter_revision_id=parameters.revision_id,
            engine_version=self._ENGINE_VERSION,
            lineages=lineages,
            validation_outcomes=validations,
            execution_assumptions=ResearchExecutionAssumptions(
                initial_cash=request.initial_cash,
                quantity=request.quantity,
                commission_bps=request.commission_bps,
                slippage_bps=request.slippage_bps,
            ),
            start=min(timestamps),
            end=max(timestamps),
            information_cutoff=max(timestamps),
            created_at=created_at,
        )
