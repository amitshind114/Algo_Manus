"""Application services for comparable multi-security research experiments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Protocol

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.application.dataset_validation import (
    ResearchDatasetValidationError,
    ResearchDatasetValidator,
)
from algo_manus.application.local_event_bus import LocalApplicationEvent, LocalEventBus, LocalEventType
from algo_manus.domain.backtest import BacktestSpec, BacktestTrade
from algo_manus.domain.experiment import (
    ExperimentBatch,
    ExperimentStatus,
    SecurityExperimentResult,
)
from algo_manus.domain.market_data import CandleDataset, DataUseCase
from algo_manus.domain.research import (
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

    def list_recent(self, limit: int = 20) -> tuple[ExperimentBatch, ...]: ...

    def get_result_artifacts(
        self, *, batch_id: str, instrument_id: str
    ) -> "ExperimentResultArtifacts | None": ...

    def get_result_artifact_integrity(
        self, *, batch_id: str, instrument_id: str
    ) -> "ExperimentArtifactIntegrity": ...


class ExperimentArtifactsUnavailableError(LookupError):
    """Raised when a persisted batch has no detailed result artifacts to inspect."""


class ExperimentArtifactIntegrityStatus(str, Enum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"
    INCOMPLETE = "incomplete"
    RESULT_SPEC_MISMATCH = "result_spec_mismatch"


@dataclass(frozen=True, slots=True)
class ExperimentArtifactIntegrity:
    """Read-only local artifact status compared against its stored experiment result."""

    batch_id: str
    instrument_id: str
    status: ExperimentArtifactIntegrityStatus
    result_spec_id: str | None
    artifact_result_spec_id: str | None
    expected_trade_count: int | None
    actual_trade_count: int
    expected_equity_point_count: int | None
    actual_equity_point_count: int

    @property
    def is_complete(self) -> bool:
        return self.status is ExperimentArtifactIntegrityStatus.COMPLETE


@dataclass(frozen=True, slots=True)
class ExperimentResultArtifacts:
    """Exact bounded local detail emitted by an already-computed fixture backtest."""

    batch_id: str
    instrument_id: str
    result_spec_id: str
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[tuple[datetime, float], ...]

    def __post_init__(self) -> None:
        if not self.batch_id or not self.instrument_id or not self.result_spec_id:
            raise ValueError("artifact batch, instrument and result spec identifiers are required")
        if any(timestamp.tzinfo is None for timestamp, _ in self.equity_curve):
            raise ValueError("artifact equity timestamps must be timezone-aware")


class ExperimentArtifactReadService:
    """Read detailed persisted evidence without recalculating a strategy or metric."""

    def __init__(self, repository: ExperimentBatchRepository) -> None:
        self._repository = repository

    def get(self, *, batch_id: str, instrument_id: str) -> ExperimentResultArtifacts:
        integrity = self.integrity(batch_id=batch_id, instrument_id=instrument_id)
        if integrity.status is ExperimentArtifactIntegrityStatus.UNAVAILABLE:
            raise ExperimentArtifactsUnavailableError(
                f"persisted detailed artifacts are unavailable for {batch_id}/{instrument_id}"
            )
        if not integrity.is_complete:
            raise ValueError(f"persisted artifact integrity status is {integrity.status.value}")
        artifacts = self._repository.get_result_artifacts(
            batch_id=batch_id, instrument_id=instrument_id
        )
        if artifacts is None:
            raise ExperimentArtifactsUnavailableError(
                f"persisted detailed artifacts are unavailable for {batch_id}/{instrument_id}"
            )
        return artifacts

    def integrity(self, *, batch_id: str, instrument_id: str) -> ExperimentArtifactIntegrity:
        return self._repository.get_result_artifact_integrity(
            batch_id=batch_id, instrument_id=instrument_id
        )


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
    def __init__(
        self,
        backtester: BarBacktestService,
        repository: ExperimentBatchRepository,
        manifest_repository: ResearchRunManifestRepository,
        validator: ResearchDatasetValidator | None = None,
        event_bus: LocalEventBus | None = None,
    ) -> None:
        self._backtester = backtester
        self._repository = repository
        self._manifest_repository = manifest_repository
        self._validator = validator or ResearchDatasetValidator()
        self._event_bus = event_bus

    def run(
        self,
        *,
        request: BatchBacktestRequest,
        strategy: Strategy,
        parameters: StrategyParameterRevision,
        created_at: datetime | None = None,
        validated_at: datetime | None = None,
    ) -> ExperimentBatch:
        datasets = tuple(request.datasets_by_instrument.values())
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
        validation_timestamp = validated_at or timestamp
        validations = tuple(
            self._validator.validate(dataset, validated_at=validation_timestamp) for dataset in datasets
        )
        rejected = tuple(outcome for outcome in validations if not outcome.research_eligible)
        if rejected:
            codes = ", ".join(
                f"{outcome.dataset_id}:{outcome.status.value}" for outcome in rejected
            )
            raise ResearchDatasetValidationError(f"research dataset validation did not accept: {codes}")
        manifest = self._manifest(request, strategy, parameters, datasets, validations, timestamp)
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
        if self._event_bus is not None:
            self._event_bus.publish(
                LocalApplicationEvent.create(
                    event_type=LocalEventType.RESEARCH_BATCH_RETAINED,
                    occurred_at=batch.created_at,
                    correlation_id=batch.batch_id,
                    producer="algo_manus.application.experiments.ExperimentBatchService",
                    attributes={
                        "source_evidence_id": manifest.manifest_id,
                        "batch_id": batch.batch_id,
                        "manifest_id": manifest.manifest_id,
                        "result_count": len(batch.results),
                    },
                )
            )
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
        validations: tuple[DatasetValidationOutcome, ...],
        created_at: datetime,
    ) -> ResearchRunManifest:
        """Construct evidence from already-validated local research inputs only."""

        lineages = tuple(DatasetLineage.from_dataset(dataset) for dataset in datasets)
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
