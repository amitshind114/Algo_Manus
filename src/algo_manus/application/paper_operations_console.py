"""Event-derived local paper-operations console read model.

This model consolidates existing immutable paper-ledger replay, paper audit and
current-process event-wiring diagnostics. It cannot submit, fill, cancel,
reconcile, publish, subscribe, synchronize or route an order.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from algo_manus.application.local_event_audit import LocalEventAuditPort, LocalEventWiringAuditReadService
from algo_manus.application.paper_audit import (
    LocalPaperOperationAuditIntegritySummary,
    LocalPaperOperationAuditRow,
    PaperAuditEventReadPort,
    PaperOperationAuditTimelineReadService,
)
from algo_manus.application.paper_projection import PaperEventReadPort, PaperOperationsReadService
from algo_manus.domain.paper import PaperPortfolioProjection


@dataclass(frozen=True, slots=True)
class LocalPaperOperationsConsoleRiskDecision:
    """Most recent retained deterministic risk-decision evidence, if interpretable."""

    allowed: bool
    decision_code: str | None
    central_decision_type: str | None
    central_decision_code: str | None


@dataclass(frozen=True, slots=True)
class LocalPaperOperationsConsoleWiring:
    """Bounded current-process wiring diagnostics; it is explicitly non-durable."""

    is_durable: bool
    maximum_retained_events: int
    retained_event_count: int
    retained_delivery_count: int
    failed_delivery_count: int
    subscriber_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalPaperOperationsConsoleSnapshot:
    """Display-safe aggregation of local evidence only; it is not an operations command plane."""

    projection: PaperPortfolioProjection
    integrity: LocalPaperOperationAuditIntegritySummary
    lifecycle_counts: Mapping[str, int]
    simulator_outcome_counts: Mapping[str, int]
    reconciliation_counts: Mapping[str, int]
    latest_risk_decision: LocalPaperOperationsConsoleRiskDecision | None
    wiring: LocalPaperOperationsConsoleWiring
    recent_events: tuple[LocalPaperOperationAuditRow, ...]


class LocalPaperOperationsConsoleReadService:
    """Read existing local evidence into one console snapshot without mutating it."""

    def __init__(self, ledger: PaperEventReadPort & PaperAuditEventReadPort, wiring: LocalEventAuditPort) -> None:
        self._operations = PaperOperationsReadService(ledger)
        self._audit = PaperOperationAuditTimelineReadService(ledger)
        self._wiring = LocalEventWiringAuditReadService(wiring)

    def snapshot(
        self,
        *,
        starting_cash: float,
        event_limit: int = 1_000,
        wiring_limit: int = 1_000,
    ) -> LocalPaperOperationsConsoleSnapshot:
        """Build one deterministic, non-actionable local operations view."""

        if event_limit <= 0 or wiring_limit <= 0:
            raise ValueError("console limits must be positive")
        projection = self._operations.portfolio(starting_cash=starting_cash, limit=event_limit)
        audit_rows = self._audit.rows(limit=event_limit)
        integrity = self._audit.integrity(limit=event_limit)
        wiring_rows = self._wiring.rows(limit=wiring_limit)
        wiring_snapshot = self._wiring.snapshot()
        return LocalPaperOperationsConsoleSnapshot(
            projection=projection,
            integrity=integrity,
            lifecycle_counts=self._frozen_counts(order.status.value for order in projection.orders),
            simulator_outcome_counts=self._frozen_counts(
                row.simulation_outcome for row in audit_rows if row.simulation_outcome is not None
            ),
            reconciliation_counts=self._frozen_counts(
                order.reconciliation_disposition.value
                for order in projection.orders
                if order.reconciliation_disposition is not None
            ),
            latest_risk_decision=self._latest_risk_decision(audit_rows),
            wiring=LocalPaperOperationsConsoleWiring(
                is_durable=wiring_snapshot.is_durable,
                maximum_retained_events=wiring_snapshot.maximum_retained_events,
                retained_event_count=wiring_snapshot.retained_event_count,
                retained_delivery_count=wiring_snapshot.retained_delivery_count,
                failed_delivery_count=sum(item.failed_subscriber_count for item in wiring_rows),
                subscriber_names=wiring_snapshot.subscriber_names,
            ),
            recent_events=audit_rows,
        )

    @staticmethod
    def _frozen_counts(values) -> Mapping[str, int]:
        return MappingProxyType(dict(sorted(Counter(values).items())))

    @staticmethod
    def _latest_risk_decision(
        rows: tuple[LocalPaperOperationAuditRow, ...]
    ) -> LocalPaperOperationsConsoleRiskDecision | None:
        for row in reversed(rows):
            if row.event_type == "RISK_DECISION" and row.payload_valid and row.decision_allowed is not None:
                return LocalPaperOperationsConsoleRiskDecision(
                    allowed=row.decision_allowed,
                    decision_code=row.decision_code,
                    central_decision_type=row.central_decision_type,
                    central_decision_code=row.central_decision_code,
                )
        return None
