"""Deterministic local validation for research datasets before experiment use."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re

from algo_manus.domain.market_data import CandleDataset, DataSourceKind, DataUseCase
from algo_manus.domain.research import (
    DataValidationIssue,
    DataValidationSeverity,
    DataValidationStatus,
    DatasetValidationOutcome,
)


class ResearchDatasetValidationError(ValueError):
    """Raised when a batch includes a dataset not accepted by the local policy."""


@dataclass(frozen=True, slots=True)
class ResearchDatasetValidationPolicy:
    """Auditable local quality policy; it is not a claim of market-data completeness."""

    policy_version: str = "research-dataset-v1"
    minimum_candles: int = 3
    maximum_gap_multiplier: float = 3.0
    permitted_source_kinds: frozenset[DataSourceKind] = field(
        default_factory=lambda: frozenset(
            {DataSourceKind.BROKER, DataSourceKind.FIXTURE, DataSourceKind.PUBLIC_FALLBACK}
        )
    )

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("validation policy version is required")
        if self.minimum_candles < 1:
            raise ValueError("minimum_candles must be positive")
        if self.maximum_gap_multiplier < 1:
            raise ValueError("maximum_gap_multiplier must be at least one")
        if not self.permitted_source_kinds:
            raise ValueError("validation policy requires at least one permitted source kind")


class ResearchDatasetValidator:
    """Produces explicit accepted, quarantined or rejected local quality evidence."""

    def __init__(self, policy: ResearchDatasetValidationPolicy | None = None) -> None:
        self._policy = policy or ResearchDatasetValidationPolicy()

    @property
    def policy(self) -> ResearchDatasetValidationPolicy:
        return self._policy

    def validate(self, dataset: CandleDataset, *, validated_at: datetime) -> DatasetValidationOutcome:
        if validated_at.tzinfo is None:
            raise ValueError("validation timestamp must be timezone-aware")
        issues: list[DataValidationIssue] = []
        if dataset.provenance.use_case is not DataUseCase.RESEARCH:
            issues.append(
                DataValidationIssue(
                    code="USE_CASE_NOT_RESEARCH",
                    severity=DataValidationSeverity.ERROR,
                    message="research validation accepts only research-use datasets",
                )
            )
        if dataset.provenance.source_kind not in self._policy.permitted_source_kinds:
            issues.append(
                DataValidationIssue(
                    code="SOURCE_KIND_NOT_PERMITTED",
                    severity=DataValidationSeverity.ERROR,
                    message="dataset source kind is not permitted by this local research policy",
                )
            )
        if len(dataset.candles) < self._policy.minimum_candles:
            issues.append(
                DataValidationIssue(
                    code="INSUFFICIENT_HISTORY",
                    severity=DataValidationSeverity.ERROR,
                    message=f"dataset has fewer than {self._policy.minimum_candles} candles",
                )
            )
        expected_gap = self._interval_duration(dataset.interval)
        if expected_gap is None:
            issues.append(
                DataValidationIssue(
                    code="UNSUPPORTED_INTERVAL_POLICY",
                    severity=DataValidationSeverity.WARNING,
                    message="local gap policy cannot evaluate this dataset interval",
                )
            )
        elif any(
            later.timestamp - earlier.timestamp > expected_gap * self._policy.maximum_gap_multiplier
            for earlier, later in zip(dataset.candles, dataset.candles[1:], strict=False)
        ):
            issues.append(
                DataValidationIssue(
                    code="GAP_EXCEEDS_POLICY",
                    severity=DataValidationSeverity.WARNING,
                    message="one or more candle gaps exceed the local interval policy",
                )
            )
        if dataset.provenance.source_kind is DataSourceKind.PUBLIC_FALLBACK:
            issues.append(
                DataValidationIssue(
                    code="PUBLIC_FALLBACK_REQUIRES_REVIEW",
                    severity=DataValidationSeverity.WARNING,
                    message="public fallback research data requires explicit review before use",
                )
            )
        status = (
            DataValidationStatus.REJECTED
            if any(issue.severity is DataValidationSeverity.ERROR for issue in issues)
            else DataValidationStatus.QUARANTINED
            if issues
            else DataValidationStatus.ACCEPTED
        )
        return DatasetValidationOutcome(
            dataset_id=dataset.dataset_id,
            status=status,
            policy_version=self._policy.policy_version,
            validated_at=validated_at,
            issues=tuple(issues),
        )

    @staticmethod
    def _interval_duration(interval: str) -> timedelta | None:
        match = re.fullmatch(r"([1-9][0-9]*)([mhd])", interval)
        if match is None:
            return None
        value = int(match.group(1))
        unit = match.group(2)
        if unit == "m":
            return timedelta(minutes=value)
        if unit == "h":
            return timedelta(hours=value)
        return timedelta(days=value)
