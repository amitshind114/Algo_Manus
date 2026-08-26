"""Read-only like-for-like comparison of retained local research batches."""

from __future__ import annotations

from dataclasses import dataclass

from algo_manus.domain.experiment import ExperimentBatch
from algo_manus.domain.research import ResearchRunManifest


@dataclass(frozen=True, slots=True)
class StrategyFamilyComparisonMember:
    """One retained research batch shown without an implied recommendation."""

    batch_id: str
    strategy_id: str
    strategy_version: str | None
    parameter_revision_id: str
    research_manifest_id: str | None
    result_count: int
    aggregate_net_pnl: float
    aggregate_trade_count: int


@dataclass(frozen=True, slots=True)
class StrategyFamilyComparison:
    """Read-only result comparison; it deliberately has no ranking or recommendation field."""

    members: tuple[StrategyFamilyComparisonMember, ...]
    is_comparable: bool
    comparison_basis: str
    comparability_reason: str


class StrategyFamilyComparisonReadService:
    """Compare already-retained batches only; it cannot run, select, promote, or trade a strategy."""

    _COMPARABLE_BASIS = "same universe, datasets, initial cash, quantity and costs"

    def compare(
        self,
        *,
        left_batch: ExperimentBatch,
        right_batch: ExperimentBatch,
        left_manifest: ResearchRunManifest | None = None,
        right_manifest: ResearchRunManifest | None = None,
    ) -> StrategyFamilyComparison:
        differences = self._differences(left_batch, right_batch, left_manifest, right_manifest)
        comparable = not differences
        reason = (
            "retained local research batches share the declared comparison basis"
            if comparable
            else "not comparable without additional review: mismatched " + ", ".join(differences)
        )
        return StrategyFamilyComparison(
            members=(
                self._member(left_batch, left_manifest),
                self._member(right_batch, right_manifest),
            ),
            is_comparable=comparable,
            comparison_basis=self._COMPARABLE_BASIS if comparable else "not like-for-like",
            comparability_reason=reason,
        )

    @staticmethod
    def _member(
        batch: ExperimentBatch,
        manifest: ResearchRunManifest | None,
    ) -> StrategyFamilyComparisonMember:
        return StrategyFamilyComparisonMember(
            batch_id=batch.batch_id,
            strategy_id=batch.strategy_id,
            strategy_version=manifest.strategy_version if manifest is not None else None,
            parameter_revision_id=batch.parameter_revision_id,
            research_manifest_id=batch.research_manifest_id,
            result_count=len(batch.results),
            aggregate_net_pnl=sum(item.backtest.metrics.net_pnl for item in batch.results),
            aggregate_trade_count=sum(item.backtest.metrics.trade_count for item in batch.results),
        )

    @classmethod
    def _differences(
        cls,
        left_batch: ExperimentBatch,
        right_batch: ExperimentBatch,
        left_manifest: ResearchRunManifest | None,
        right_manifest: ResearchRunManifest | None,
    ) -> tuple[str, ...]:
        differences: list[str] = []
        if left_batch.universe_id != right_batch.universe_id:
            differences.append("universe_id")
        if left_batch.universe_snapshot_id != right_batch.universe_snapshot_id:
            differences.append("universe_snapshot_id")
        left_by_instrument = {item.instrument_id: item for item in left_batch.results}
        right_by_instrument = {item.instrument_id: item for item in right_batch.results}
        if set(left_by_instrument) != set(right_by_instrument):
            differences.append("instrument_set")
            return tuple(differences)
        for instrument_id in sorted(left_by_instrument):
            left = left_by_instrument[instrument_id].backtest.spec
            right = right_by_instrument[instrument_id].backtest.spec
            for field in ("dataset_id", "initial_cash", "quantity", "commission_bps", "slippage_bps", "force_close_at_end"):
                if getattr(left, field) != getattr(right, field) and field not in differences:
                    differences.append(field)
        if left_manifest is not None and right_manifest is not None:
            if left_manifest.execution_assumptions.execution_timing != right_manifest.execution_assumptions.execution_timing:
                differences.append("execution_timing")
        return tuple(differences)
