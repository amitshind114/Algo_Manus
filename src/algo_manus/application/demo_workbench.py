"""Clearly labelled deterministic fixture mode for the local research workbench.

The sample instruments and candles in this module are workflow fixtures. They
are not market data, are not broker data and must not be treated as evidence of
strategy performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Mapping

from algo_manus.application.backtesting import BarBacktestService
from algo_manus.application.experiment_evidence import ExperimentEvidenceReadService
from algo_manus.application.experiment_export import (
    ExperimentEvidenceExport,
    ExperimentEvidenceExportService,
)
from algo_manus.application.evidence_lifecycle import LocalEvidenceLifecycle, LocalEvidenceLifecycleReadService
from algo_manus.application.evidence_health import LocalEvidenceHealth, LocalEvidenceHealthReadService
from algo_manus.application.evidence_health_detail import (
    LocalEvidenceHealthDetail,
    LocalEvidenceHealthDetailReadService,
)
from algo_manus.application.evidence_health_history import (
    LocalEvidenceHealthHistoryReadService,
    LocalEvidenceHealthHistoryRow,
)
from algo_manus.application.evidence_health_scope import (
    LocalEvidenceHealthScope,
    LocalEvidenceHealthScopeReadService,
)
from algo_manus.application.evidence_health_comparison import (
    LocalEvidenceHealthComparison,
    LocalEvidenceHealthComparisonReadService,
)
from algo_manus.application.experiments import (
    BatchBacktestRequest,
    ExperimentArtifactReadService,
    ExperimentArtifactIntegrity,
    ExperimentArtifactIntegrityStatus,
    ExperimentBatchService,
    ExperimentResultArtifacts,
)
from algo_manus.application.leaderboard import LeaderboardService, LeaderboardSort
from algo_manus.application.local_event_bus import LocalEventBus
from algo_manus.application.paper_promotion import PaperResearchPromotionService
from algo_manus.application.robustness import (
    LocalRobustnessEvaluationService,
    RobustnessEvidence,
    RobustnessGrid,
    RobustnessSplitPolicy,
)
from algo_manus.application.strategy_family_comparison import (
    StrategyFamilyComparison,
    StrategyFamilyComparisonReadService,
)
from algo_manus.domain.experiment import ExperimentBatch
from algo_manus.domain.market_data import (
    Candle,
    CandleDataset,
    DataProvenance,
    DataSourceKind,
    DataUseCase,
)
from algo_manus.domain.strategy import StrategyParameterRevision
from algo_manus.domain.research import ResearchRunManifest
from algo_manus.strategies.registry import built_in_registry

FIXTURE_MODE_LABEL = "Fixture mode — deterministic local sample data; not broker or market data"


@dataclass(frozen=True, slots=True)
class FixtureInstrument:
    instrument_id: str
    symbol: str
    display_name: str
    segment: str


class _MemoryExperimentRepository:
    def __init__(self) -> None:
        self._batches: dict[str, ExperimentBatch] = {}

    def save(self, batch: ExperimentBatch) -> None:
        self._batches[batch.batch_id] = batch

    def get(self, batch_id: str) -> ExperimentBatch | None:
        return self._batches.get(batch_id)

    def list_recent(self, limit: int = 20) -> tuple[ExperimentBatch, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        return tuple(sorted(self._batches.values(), key=lambda item: (item.created_at, item.batch_id), reverse=True)[:limit])

    def get_result_artifacts(
        self, *, batch_id: str, instrument_id: str
    ) -> ExperimentResultArtifacts | None:
        batch = self._batches.get(batch_id)
        if batch is None:
            return None
        result = next((item.backtest for item in batch.results if item.instrument_id == instrument_id), None)
        if result is None:
            return None
        return ExperimentResultArtifacts(
            batch_id=batch_id,
            instrument_id=instrument_id,
            result_spec_id=result.spec.spec_id,
            trades=result.trades,
            equity_curve=result.equity_curve,
        )

    def get_result_artifact_integrity(
        self, *, batch_id: str, instrument_id: str
    ) -> ExperimentArtifactIntegrity:
        batch = self._batches.get(batch_id)
        result = (
            next((item.backtest for item in batch.results if item.instrument_id == instrument_id), None)
            if batch is not None
            else None
        )
        if result is None:
            return ExperimentArtifactIntegrity(
                batch_id=batch_id,
                instrument_id=instrument_id,
                status=ExperimentArtifactIntegrityStatus.UNAVAILABLE,
                result_spec_id=None,
                artifact_result_spec_id=None,
                expected_trade_count=None,
                actual_trade_count=0,
                expected_equity_point_count=None,
                actual_equity_point_count=0,
            )
        return ExperimentArtifactIntegrity(
            batch_id=batch_id,
            instrument_id=instrument_id,
            status=ExperimentArtifactIntegrityStatus.COMPLETE,
            result_spec_id=result.spec.spec_id,
            artifact_result_spec_id=result.spec.spec_id,
            expected_trade_count=len(result.trades),
            actual_trade_count=len(result.trades),
            expected_equity_point_count=len(result.equity_curve),
            actual_equity_point_count=len(result.equity_curve),
        )

    def lifecycle_snapshot(self) -> LocalEvidenceLifecycle:
        batches = tuple(self._batches.values())
        results = tuple(result for batch in batches for result in batch.results)
        created_at = tuple(batch.created_at for batch in batches)
        return LocalEvidenceLifecycle(
            is_persistent=False,
            database_path=None,
            database_size_bytes=0,
            batch_count=len(batches),
            result_count=len(results),
            artifact_count=len(results),
            completed_trade_count=sum(len(result.backtest.trades) for result in results),
            equity_point_count=sum(len(result.backtest.equity_curve) for result in results),
            oldest_batch_created_at=min(created_at) if created_at else None,
            newest_batch_created_at=max(created_at) if created_at else None,
            max_equity_points_per_result=None,
            max_trades_per_result=None,
        )

    def evidence_health_snapshot(self) -> LocalEvidenceHealth:
        results = tuple(result for batch in self._batches.values() for result in batch.results)
        return LocalEvidenceHealth(
            total_result_count=len(results),
            complete_count=len(results),
            unavailable_count=0,
            incomplete_count=0,
            result_spec_mismatch_count=0,
        )

    def evidence_health_details(self) -> tuple[LocalEvidenceHealthDetail, ...]:
        return tuple(
            LocalEvidenceHealthDetail(
                batch_id=batch.batch_id,
                instrument_id=result.instrument_id,
                created_at=batch.created_at,
                status=ExperimentArtifactIntegrityStatus.COMPLETE,
                result_spec_id=result.backtest.spec.spec_id,
                artifact_result_spec_id=result.backtest.spec.spec_id,
                expected_trade_count=len(result.backtest.trades),
                actual_trade_count=len(result.backtest.trades),
                expected_equity_point_count=len(result.backtest.equity_curve),
                actual_equity_point_count=len(result.backtest.equity_curve),
            )
            for batch in sorted(self._batches.values(), key=lambda item: item.created_at, reverse=True)
            for result in batch.results
        )


class _MemoryResearchManifestRepository:
    """Fixture-only evidence repository; Streamlit state still owns visible history."""

    def __init__(self) -> None:
        self._manifests: dict[str, ResearchRunManifest] = {}

    def save(self, manifest: ResearchRunManifest) -> None:
        self._manifests.setdefault(manifest.manifest_id, manifest)

    def get(self, manifest_id: str) -> ResearchRunManifest | None:
        return self._manifests.get(manifest_id)

    def list_recent(self, limit: int = 20) -> tuple[ResearchRunManifest, ...]:
        return tuple(self._manifests.values())[-limit:]


class _MemoryRobustnessEvidenceRepository:
    """Fixture-only retained robustness records for a single local process."""

    def __init__(self) -> None:
        self._evidence: dict[str, RobustnessEvidence] = {}

    def save(self, evidence: RobustnessEvidence) -> None:
        existing = self._evidence.get(evidence.evidence_id)
        if existing is not None and existing != evidence:
            raise ValueError("immutable robustness evidence conflicts with existing record")
        self._evidence.setdefault(evidence.evidence_id, evidence)

    def get(self, evidence_id: str) -> RobustnessEvidence | None:
        return self._evidence.get(evidence_id)

    def list_recent(self, limit: int = 20) -> tuple[RobustnessEvidence, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        return tuple(
            sorted(self._evidence.values(), key=lambda item: (item.created_at, item.evidence_id), reverse=True)[:limit]
        )


class FixtureWorkbenchService:
    """Uses the production application services with deterministic local inputs."""

    _SERIES: Mapping[str, tuple[float, ...]] = {
        "FIXTURE:NSE:EQ:ALPHA": (100, 98, 96, 97, 101, 106, 110, 107, 103, 99, 96, 98, 102, 108, 113),
        "FIXTURE:NSE:EQ:BRAVO": (80, 79, 78, 80, 82, 84, 83, 81, 79, 78, 77, 79, 82, 86, 90),
        "FIXTURE:NSE:EQ:CEDAR": (120, 122, 124, 126, 127, 125, 123, 120, 118, 116, 114, 112, 110, 109, 108),
        "FIXTURE:NSE:EQ:DELTA": (60, 58, 57, 59, 63, 67, 70, 68, 66, 64, 65, 68, 72, 76, 80),
        "FIXTURE:NSE:EQ:EMBER": (150, 148, 145, 147, 150, 154, 151, 148, 146, 149, 153, 157, 161, 158, 155),
    }
    _META: Mapping[str, tuple[str, str]] = {
        "FIXTURE:NSE:EQ:ALPHA": ("ALPHA", "Fixture Alpha Industries"),
        "FIXTURE:NSE:EQ:BRAVO": ("BRAVO", "Fixture Bravo Systems"),
        "FIXTURE:NSE:EQ:CEDAR": ("CEDAR", "Fixture Cedar Manufacturing"),
        "FIXTURE:NSE:EQ:DELTA": ("DELTA", "Fixture Delta Logistics"),
        "FIXTURE:NSE:EQ:EMBER": ("EMBER", "Fixture Ember Consumer"),
    }
    _ROBUSTNESS_SERIES: Mapping[str, tuple[float, ...]] = {
        "FIXTURE:NSE:EQ:ALPHA": (
            100, 98, 96, 97, 101, 106, 110, 107, 103, 99,
            96, 98, 102, 108, 113, 110, 106, 103, 100, 104,
            109, 114, 117, 113, 108, 105, 101, 104, 109, 115,
        ),
    }

    def __init__(self, data_root: Path | None = None, event_bus: LocalEventBus | None = None) -> None:
        self._event_bus = event_bus or LocalEventBus()
        if data_root is None:
            self._batches = _MemoryExperimentRepository()
            self._manifests = _MemoryResearchManifestRepository()
            self._robustness = _MemoryRobustnessEvidenceRepository()
        else:
            from algo_manus.infrastructure.experiments.sqlite_repository import SqliteExperimentBatchRepository
            from algo_manus.infrastructure.research.sqlite_repository import SqliteResearchEvidenceRepository
            from algo_manus.infrastructure.robustness.sqlite_repository import SqliteRobustnessEvidenceRepository

            self._batches = SqliteExperimentBatchRepository(data_root / "experiments.sqlite3")
            self._manifests = SqliteResearchEvidenceRepository(data_root / "research_evidence.sqlite3")
            self._robustness = SqliteRobustnessEvidenceRepository(data_root / "robustness_evidence.sqlite3")

    def instruments(self) -> tuple[FixtureInstrument, ...]:
        return tuple(
            FixtureInstrument(instrument_id, symbol, name, "NSE Equity fixture")
            for instrument_id, (symbol, name) in self._META.items()
        )

    def strategy_catalog(self):
        """Return display-safe metadata for the explicitly registered local strategies."""

        return built_in_registry().metadata()

    def validate_strategy_parameters(
        self, strategy_id: str, parameters: Mapping[str, int | float]
    ) -> Mapping[str, int | float]:
        """Validate UI-supplied parameters through the shared strategy contract."""

        return built_in_registry().validate_parameters(strategy_id, parameters)

    def run_experiment(
        self,
        *,
        selected_instrument_ids: tuple[str, ...],
        fast_window: int | None = None,
        slow_window: int | None = None,
        strategy_id: str = "sma_crossover",
        parameters: Mapping[str, int | float] | None = None,
        initial_cash: float,
        quantity: int,
        commission_bps: float,
        slippage_bps: float,
    ) -> ExperimentBatch:
        if not selected_instrument_ids:
            raise ValueError("select at least one fixture instrument")
        if set(selected_instrument_ids) - set(self._SERIES):
            raise ValueError("selected fixture instrument is unknown")
        registry = built_in_registry()
        strategy = registry.get(strategy_id)
        if parameters is None:
            parameters = dict(strategy.metadata.parameter_schema.defaults())
            if strategy_id == "sma_crossover":
                if fast_window is None or slow_window is None:
                    raise ValueError("SMA runs require fast_window and slow_window")
                parameters.update(fast_window=fast_window, slow_window=slow_window)
        try:
            normalized = registry.validate_parameters(strategy_id, parameters)
        except ValueError as exc:
            if strategy_id == "sma_crossover" and "fast_window" in str(exc):
                raise ValueError(f"fast window validation failed: {exc}") from exc
            raise
        parameter_revision = StrategyParameterRevision.create(strategy_id, normalized)
        datasets = {instrument_id: self._dataset(instrument_id) for instrument_id in selected_instrument_ids}
        return ExperimentBatchService(
            BarBacktestService(),
            self._batches,
            self._manifests,
            event_bus=self._event_bus,
        ).run(
            request=BatchBacktestRequest(
                universe_id="fixture-nse-equity-universe",
                universe_snapshot_id="FIXTURE-SNAPSHOT-LOCAL-V1",
                datasets_by_instrument=datasets,
                initial_cash=initial_cash,
                quantity=quantity,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
            ),
            strategy=strategy,
            parameters=parameter_revision,
            created_at=datetime.now(timezone.utc),
            validated_at=datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc),
        )

    def local_event_bus(self) -> LocalEventBus:
        """Return the local process bus for application-service composition only."""

        return self._event_bus

    def paper_promotion(self, *, batch_id: str, instrument_id: str):
        """Return exact persisted manifest/validation evidence, or ``None`` when absent."""

        return PaperResearchPromotionService(
            ExperimentEvidenceReadService(self._batches, self._manifests)
        ).resolve(batch_id=batch_id, instrument_id=instrument_id)

    def strategy_family_comparison(
        self,
        *,
        left_batch_id: str,
        right_batch_id: str,
    ) -> StrategyFamilyComparison:
        """Compare two retained local research batches without ranking or promoting either one."""

        left_batch = self._batches.get(left_batch_id)
        right_batch = self._batches.get(right_batch_id)
        if left_batch is None or right_batch is None:
            raise LookupError("both retained experiment batches are required for comparison")
        left_manifest = (
            self._manifests.get(left_batch.research_manifest_id)
            if left_batch.research_manifest_id is not None
            else None
        )
        right_manifest = (
            self._manifests.get(right_batch.research_manifest_id)
            if right_batch.research_manifest_id is not None
            else None
        )
        return StrategyFamilyComparisonReadService().compare(
            left_batch=left_batch,
            right_batch=right_batch,
            left_manifest=left_manifest,
            right_manifest=right_manifest,
        )

    def run_local_robustness_evaluation(self, *, instrument_id: str) -> RobustnessEvidence:
        """Run a fixed, bounded research-only robustness evaluation for one declared fixture.

        The workbench intentionally exposes neither candidate selection nor
        promotion from this method. It only retains local evidence for display.
        """

        if instrument_id not in self._ROBUSTNESS_SERIES:
            raise ValueError("robustness evaluation is available only for the declared ALPHA fixture series")
        return LocalRobustnessEvaluationService(self._robustness).evaluate(
            dataset=self._robustness_dataset(instrument_id),
            strategy=built_in_registry().get("sma_crossover"),
            grid=RobustnessGrid({"fast_window": (2, 3), "slow_window": (5, 6)}),
            split_policy=RobustnessSplitPolicy(in_sample_ratio=0.6, max_grid_cells=4),
            initial_cash=100_000,
            quantity=100,
            commission_bps=10,
            slippage_bps=5,
            created_at=datetime(2026, 8, 26, 9, 15, tzinfo=timezone.utc),
        )

    def recent_robustness_evidence(self, limit: int = 20) -> tuple[RobustnessEvidence, ...]:
        """Return retained robustness evidence only; this never ranks, promotes or trades."""

        return self._robustness.list_recent(limit)

    def recent_experiments(self, limit: int = 20) -> tuple[ExperimentBatch, ...]:
        """Return local persisted fixture batches newest-first for restart-safe workbench history."""

        return self._batches.list_recent(limit)

    def experiment_artifacts(
        self, *, batch_id: str, instrument_id: str
    ) -> ExperimentResultArtifacts:
        """Read stored fixture detail; this never reruns a strategy or loads market data."""

        return ExperimentArtifactReadService(self._batches).get(
            batch_id=batch_id,
            instrument_id=instrument_id,
        )

    def experiment_artifact_integrity(
        self, *, batch_id: str, instrument_id: str
    ) -> ExperimentArtifactIntegrity:
        """Return a local stored-artifact status without rerunning fixture research."""

        return ExperimentArtifactReadService(self._batches).integrity(
            batch_id=batch_id,
            instrument_id=instrument_id,
        )

    def evidence_export(self, *, batch_id: str) -> ExperimentEvidenceExport:
        """Build a local fixture evidence export; detailed content remains integrity-gated."""

        export = ExperimentEvidenceExportService(self._batches).get(batch_id=batch_id)
        if export is None:
            raise LookupError(f"persisted experiment is unavailable: {batch_id}")
        return export

    def evidence_lifecycle(self) -> LocalEvidenceLifecycle:
        """Return local store metadata only; no cleanup or retention action is performed."""

        return LocalEvidenceLifecycleReadService(self._batches).snapshot()

    def evidence_health(self) -> LocalEvidenceHealth:
        """Return aggregate local artifact status only; no records are repaired or changed."""

        return LocalEvidenceHealthReadService(self._batches).snapshot()

    def evidence_health_details(self) -> tuple[LocalEvidenceHealthDetail, ...]:
        """List retained local artifact status context only; no result is changed."""

        return LocalEvidenceHealthDetailReadService(self._batches).list()

    def evidence_health_history(self) -> tuple[LocalEvidenceHealthHistoryRow, ...]:
        """Return chronological retained local health coverage only; no result is changed."""

        return LocalEvidenceHealthHistoryReadService(self._batches).list()

    def evidence_health_scope(
        self,
        *,
        batch_id: str | None = None,
        created_from: datetime | None = None,
        created_until: datetime | None = None,
    ) -> LocalEvidenceHealthScope:
        """Filter retained local health evidence only; no record or workflow is changed."""

        return LocalEvidenceHealthScopeReadService(self._batches).read(
            batch_id=batch_id,
            created_from=created_from,
            created_until=created_until,
        )

    def evidence_health_comparison(
        self,
        *,
        left_batch_id: str,
        right_batch_id: str,
    ) -> LocalEvidenceHealthComparison:
        """Compare two retained local batches only; no evidence or workflow is changed."""

        return LocalEvidenceHealthComparisonReadService(self._batches).compare(
            left_batch_id=left_batch_id,
            right_batch_id=right_batch_id,
        )

    @staticmethod
    def leaderboard(batch: ExperimentBatch, sort_by: LeaderboardSort):
        return LeaderboardService().rows(batch, sort_by)

    def _dataset(self, instrument_id: str) -> CandleDataset:
        start = datetime(2026, 7, 1, 9, 15, tzinfo=timezone.utc)
        candles = tuple(
            Candle(
                timestamp=start + timedelta(days=index),
                open=close - 0.4,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=10_000 + index * 200,
            )
            for index, close in enumerate(self._SERIES[instrument_id])
        )
        return CandleDataset.create(
            instrument_id=instrument_id,
            interval="1d",
            provenance=DataProvenance(
                source_name="algo-manus-fixture-workbench",
                source_kind=DataSourceKind.FIXTURE,
                source_uri="fixture://algo-manus/local-workbench-v1",
                retrieved_at=start,
                raw_content_sha256=sha256(f"fixture-workbench:{instrument_id}".encode()).hexdigest(),
                adjustment_basis="synthetic unadjusted fixture bars",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=candles,
        )

    def _robustness_dataset(self, instrument_id: str) -> CandleDataset:
        """Return a longer, clearly labeled deterministic fixture solely for gate demonstration."""

        start = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
        candles = tuple(
            Candle(
                timestamp=start + timedelta(days=index),
                open=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=10_000,
            )
            for index, close in enumerate(self._ROBUSTNESS_SERIES[instrument_id])
        )
        return CandleDataset.create(
            instrument_id=instrument_id,
            interval="1d",
            provenance=DataProvenance(
                source_name="algo-manus-robustness-fixture",
                source_kind=DataSourceKind.FIXTURE,
                source_uri="fixture://algo-manus/robustness-gate-v1",
                retrieved_at=start,
                raw_content_sha256=sha256(f"robustness-fixture:{instrument_id}".encode()).hexdigest(),
                adjustment_basis="synthetic unadjusted fixture bars; not market evidence",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=candles,
        )
