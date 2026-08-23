"""Read-only local audit rows for durable paper-operation ledger events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Protocol

from algo_manus.domain.paper import PaperEvent, PaperOrderLifecycle, PaperOrderStatus


class PaperAuditEventReadPort(Protocol):
    def events(self, limit: int = 1_000) -> tuple[PaperEvent, ...]: ...

    def events_for(self, order_id: str) -> tuple[PaperEvent, ...]: ...

    def order_ids(self) -> frozenset[str]: ...


@dataclass(frozen=True, slots=True)
class LocalPaperOperationAuditRow:
    event_id: str
    occurred_at: datetime
    event_type: str
    lifecycle_state: str
    order_id: str
    instrument_id: str
    payload_valid: bool
    integrity_status: str
    side: str | None
    quantity: int | None
    reference_price: float | None
    fill_price: float | None
    decision_allowed: bool | None
    decision_code: str | None
    central_decision_type: str | None
    central_decision_code: str | None
    research_batch_id: str | None
    research_manifest_id: str | None
    research_dataset_id: str | None
    research_validation_policy_version: str | None


@dataclass(frozen=True, slots=True)
class LocalPaperOperationAuditIntegritySummary:
    total_events: int
    valid_events: int
    malformed_payload_events: int
    invalid_lifecycle_events: int


class PaperOperationAuditTimelineReadService:
    """Interpret retained local ledger events only; it cannot submit, cancel or modify orders."""

    def __init__(self, ledger: PaperAuditEventReadPort) -> None:
        self._ledger = ledger

    def rows(
        self, limit: int = 1_000, order_id: str | None = None
    ) -> tuple[LocalPaperOperationAuditRow, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        states: dict[str, PaperOrderStatus] = {}
        rows: list[LocalPaperOperationAuditRow] = []
        for event in self._events(limit=limit, order_id=order_id):
            current = states.get(event.order_id, PaperOrderStatus.PENDING_RISK)
            next_state = PaperOrderLifecycle.apply(current, event.event_type)
            lifecycle_state = "UNPROJECTABLE" if next_state is None else next_state.value
            if next_state is not None:
                states[event.order_id] = next_state
            payload, payload_valid = self._payload(event.payload)
            rows.append(
                LocalPaperOperationAuditRow(
                    event_id=event.event_id,
                    occurred_at=event.occurred_at,
                    event_type=event.event_type.value,
                    lifecycle_state=lifecycle_state,
                    order_id=event.order_id,
                    instrument_id=event.instrument_id,
                    payload_valid=payload_valid,
                    integrity_status=self._integrity_status(payload_valid, next_state is not None),
                    side=self._string(payload, "side"),
                    quantity=self._positive_int(payload, "quantity"),
                    reference_price=self._positive_number(payload, "reference_price"),
                    fill_price=self._positive_number(payload, "fill_price"),
                    decision_allowed=self._boolean(payload, "allowed"),
                    decision_code=self._string(payload, "code"),
                    central_decision_type=self._string(payload, "central_decision_type"),
                    central_decision_code=self._string(payload, "central_decision_code"),
                    research_batch_id=self._string(payload, "research_batch_id"),
                    research_manifest_id=self._string(payload, "research_manifest_id"),
                    research_dataset_id=self._string(payload, "research_dataset_id"),
                    research_validation_policy_version=self._string(
                        payload, "research_validation_policy_version"
                    ),
                )
            )
        return tuple(rows)

    def integrity(
        self, limit: int = 1_000, order_id: str | None = None
    ) -> LocalPaperOperationAuditIntegritySummary:
        rows = self.rows(limit=limit, order_id=order_id)
        return LocalPaperOperationAuditIntegritySummary(
            total_events=len(rows),
            valid_events=sum(item.integrity_status == "VALID" for item in rows),
            malformed_payload_events=sum(not item.payload_valid for item in rows),
            invalid_lifecycle_events=sum(item.lifecycle_state == "UNPROJECTABLE" for item in rows),
        )

    def _events(self, *, limit: int, order_id: str | None) -> tuple[PaperEvent, ...]:
        if order_id is None:
            return self._ledger.events(limit)
        retained_order_id = order_id.strip()
        if not retained_order_id:
            raise ValueError("order_id must not be blank")
        if retained_order_id not in self._ledger.order_ids():
            raise ValueError("unknown retained order_id")
        return self._ledger.events_for(retained_order_id)[:limit]

    @staticmethod
    def _payload(serialized: str) -> tuple[dict[str, object], bool]:
        try:
            canonical = json.loads(serialized)
        except (TypeError, json.JSONDecodeError):
            return {}, False
        payload = canonical.get("payload") if isinstance(canonical, dict) else None
        return (payload, True) if isinstance(payload, dict) else ({}, False)

    @staticmethod
    def _integrity_status(payload_valid: bool, lifecycle_valid: bool) -> str:
        if payload_valid and lifecycle_valid:
            return "VALID"
        if not payload_valid and not lifecycle_valid:
            return "MALFORMED_PAYLOAD_AND_INVALID_LIFECYCLE"
        if not payload_valid:
            return "MALFORMED_PAYLOAD"
        return "INVALID_LIFECYCLE"

    @staticmethod
    def _string(payload: dict[str, object], field: str) -> str | None:
        value = payload.get(field)
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _positive_int(payload: dict[str, object], field: str) -> int | None:
        value = payload.get(field)
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    @staticmethod
    def _positive_number(payload: dict[str, object], field: str) -> float | None:
        value = payload.get(field)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None

    @staticmethod
    def _boolean(payload: dict[str, object], field: str) -> bool | None:
        value = payload.get(field)
        return value if isinstance(value, bool) else None
