"""Research-only backtesting over one explicitly selected retained broker dataset.

This service reads already persisted local evidence only.  It does not fetch
broker data, construct a substitute fixture dataset, access an account or
expose any execution capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.application.dataset_validation import ResearchDatasetValidationError, ResearchDatasetValidator
from algo_manus.application.experiments import BatchBacktestRequest, ExperimentBatchRepository, ExperimentBatchService
from algo_manus.domain.experiment import ExperimentBatch
from algo_manus.domain.market_data import CandleDataset, DataSourceKind, DataUseCase
from algo_manus.domain.research import DatasetValidationOutcome, ResearchRunManifestRepository
from algo_manus.domain.strategy import StrategyParameterRevision
from algo_manus.infrastructure.market_data.ports import CandleDatasetRepository
from algo_manus.strategies.registry import built_in_registry


@dataclass(frozen=True, slots=True)
class RetainedDatasetBacktestRequest:
    """Explicit local selection and execution inputs for one broker dataset."""

    dataset_id: str
    strategy_id: str
    parameters: Mapping[str, int | float]
    initial_cash: float
    quantity: int
    commission_bps: float
    slippage_bps: float

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.strategy_id.strip():
            raise ValueError("retained dataset and strategy identities are required")
        if self.initial_cash <= 0 or self.quantity <= 0:
            raise ValueError("initial_cash and quantity must be positive")
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("commission_bps and slippage_bps cannot be negative")


@dataclass(frozen=True, slots=True)
class RetainedDatasetBacktestRun:
    """Read-safe result linking selected source evidence to its persisted batch."""

    dataset: CandleDataset
    validation: DatasetValidationOutcome
    batch: ExperimentBatch


class RetainedDatasetBacktestService:
    """Run a single explicitly selected retained Angel broker dataset.

    The service requires a broker/research dataset whose source is Angel One,
    validates it before invoking the existing next-bar engine, and pins its
    exact dataset id, raw-content hash and validation outcome in the existing
    immutable research manifest.  It intentionally does not create a fixture
    fallback, multi-dataset synthetic universe or any provider request.
    """

    def __init__(
        self,
        candle_repository: CandleDatasetRepository,
        batch_repository: ExperimentBatchRepository,
        manifest_repository: ResearchRunManifestRepository,
        validator: ResearchDatasetValidator | None = None,
    ) -> None:
        self._candle_repository = candle_repository
        self._validator = validator or ResearchDatasetValidator()
        self._batch_service = ExperimentBatchService(
            BarBacktestService(),
            batch_repository,
            manifest_repository,
            validator=self._validator,
        )

    def available_datasets(self, *, limit: int = 20) -> tuple[CandleDataset, ...]:
        """List bounded retained Angel evidence only; never fetch or normalize data."""

        return self._candle_repository.list_recent(source_name="angel_one", limit=limit)

    def run(
        self,
        request: RetainedDatasetBacktestRequest,
        *,
        now: datetime | None = None,
    ) -> RetainedDatasetBacktestRun:
        """Validate and backtest the caller-selected retained dataset once."""

        timestamp = now or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        dataset = self._candle_repository.get(request.dataset_id)
        if dataset is None:
            raise LookupError("selected retained historical dataset is unavailable")
        self._assert_approved_dataset(dataset)
        validation = self._validator.validate(dataset, validated_at=timestamp)
        if not validation.research_eligible:
            raise ResearchDatasetValidationError(
                "selected retained historical dataset is not accepted by the local research policy"
            )
        registry = built_in_registry()
        strategy = registry.get(request.strategy_id)
        parameters = registry.validate_parameters(request.strategy_id, request.parameters)
        revision = StrategyParameterRevision.create(request.strategy_id, parameters)
        batch = self._batch_service.run(
            request=BatchBacktestRequest(
                universe_id=f"retained-broker-dataset:{dataset.instrument_id}",
                universe_snapshot_id=f"DATASET:{dataset.dataset_id}",
                datasets_by_instrument={dataset.instrument_id: dataset},
                initial_cash=request.initial_cash,
                quantity=request.quantity,
                commission_bps=request.commission_bps,
                slippage_bps=request.slippage_bps,
            ),
            strategy=strategy,
            parameters=revision,
            created_at=timestamp,
            validated_at=timestamp,
        )
        return RetainedDatasetBacktestRun(dataset=dataset, validation=validation, batch=batch)

    @staticmethod
    def _assert_approved_dataset(dataset: CandleDataset) -> None:
        if dataset.provenance.source_name != "angel_one" or dataset.provenance.source_kind is not DataSourceKind.BROKER:
            raise ValueError("retained-dataset backtests require an Angel One broker historical dataset")
        if dataset.provenance.use_case is not DataUseCase.RESEARCH:
            raise ValueError("retained-dataset backtests require a research-use dataset")
        if dataset.provenance.retrieved_at < dataset.candles[-1].timestamp:
            raise ValueError("retained dataset retrieval time predates its final candle")
