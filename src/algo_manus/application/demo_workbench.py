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
from algo_manus.application.experiments import BatchBacktestRequest, ExperimentBatchService
from algo_manus.application.leaderboard import LeaderboardService, LeaderboardSort
from algo_manus.application.paper_promotion import PaperResearchPromotionService
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
from algo_manus.strategies.sma_crossover import SmaCrossoverStrategy

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

    def __init__(self, data_root: Path | None = None) -> None:
        if data_root is None:
            self._batches = _MemoryExperimentRepository()
            self._manifests = _MemoryResearchManifestRepository()
        else:
            from algo_manus.infrastructure.experiments.sqlite_repository import SqliteExperimentBatchRepository
            from algo_manus.infrastructure.research.sqlite_repository import SqliteResearchEvidenceRepository

            self._batches = SqliteExperimentBatchRepository(data_root / "experiments.sqlite3")
            self._manifests = SqliteResearchEvidenceRepository(data_root / "research_evidence.sqlite3")

    def instruments(self) -> tuple[FixtureInstrument, ...]:
        return tuple(
            FixtureInstrument(instrument_id, symbol, name, "NSE Equity fixture")
            for instrument_id, (symbol, name) in self._META.items()
        )

    def run_experiment(
        self,
        *,
        selected_instrument_ids: tuple[str, ...],
        fast_window: int,
        slow_window: int,
        initial_cash: float,
        quantity: int,
        commission_bps: float,
        slippage_bps: float,
    ) -> ExperimentBatch:
        if not selected_instrument_ids:
            raise ValueError("select at least one fixture instrument")
        if fast_window >= slow_window:
            raise ValueError("fast window must be smaller than slow window")
        if set(selected_instrument_ids) - set(self._SERIES):
            raise ValueError("selected fixture instrument is unknown")
        parameters = StrategyParameterRevision.create(
            "sma_crossover", {"fast_window": fast_window, "slow_window": slow_window}
        )
        datasets = {instrument_id: self._dataset(instrument_id) for instrument_id in selected_instrument_ids}
        return ExperimentBatchService(
            BarBacktestService(),
            self._batches,
            self._manifests,
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
            strategy=SmaCrossoverStrategy(),
            parameters=parameters,
            created_at=datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc),
        )

    def paper_promotion(self, *, batch_id: str, instrument_id: str):
        """Return exact persisted manifest/validation evidence, or ``None`` when absent."""

        return PaperResearchPromotionService(
            ExperimentEvidenceReadService(self._batches, self._manifests)
        ).resolve(batch_id=batch_id, instrument_id=instrument_id)

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
