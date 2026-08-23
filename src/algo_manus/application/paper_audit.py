"""Read-only local audit rows for durable paper-operation ledger events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Protocol

from algo_manus.domain.paper import PaperEvent, PaperEventType, PaperOrderLifecycle, PaperOrderStatus


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
        self,
        limit: int = 1_000,
        order_id: str | None = None,
        integrity_filter: str | None = None,
        event_type_filter: str | None = None,
        instrument_id_filter: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[LocalPaperOperationAuditRow, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        integrity_scope = self._integrity_scope(integrity_filter)
        event_type_scope = self._event_type_scope(event_type_filter)
        time_window = self._time_window(start_time, end_time)
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
        instrument_scope = self._instrument_scope(instrument_id_filter, rows)
        return tuple(
            row
            for row in rows
            if self._matches_integrity_scope(row, integrity_scope)
            and self._matches_event_type_scope(row, event_type_scope)
            and self._matches_instrument_scope(row, instrument_scope)
            and self._matches_time_window(row, time_window)
        )

    def integrity(
        self,
        limit: int = 1_000,
        order_id: str | None = None,
        integrity_filter: str | None = None,
        event_type_filter: str | None = None,
        instrument_id_filter: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> LocalPaperOperationAuditIntegritySummary:
        rows = self.rows(
            limit=limit,
            order_id=order_id,
            integrity_filter=integrity_filter,
            event_type_filter=event_type_filter,
            instrument_id_filter=instrument_id_filter,
            start_time=start_time,
            end_time=end_time,
        )
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
    def _integrity_scope(integrity_filter: str | None) -> str:
        if integrity_filter is None:
            return "ALL"
        normalized = integrity_filter.strip().upper()
        if not normalized:
            raise ValueError("integrity_filter must not be blank")
        if normalized not in {"ALL", "VALID", "ISSUES"}:
            raise ValueError("unknown integrity_filter")
        return normalized

    @staticmethod
    def _matches_integrity_scope(row: LocalPaperOperationAuditRow, scope: str) -> bool:
        if scope == "ALL":
            return True
        if scope == "VALID":
            return row.integrity_status == "VALID"
        return row.integrity_status != "VALID"

    @staticmethod
    def _event_type_scope(event_type_filter: str | None) -> str:
        if event_type_filter is None:
            return "ALL"
        normalized = event_type_filter.strip().upper()
        if not normalized:
            raise ValueError("event_type_filter must not be blank")
        if normalized not in {"ALL", *(event_type.value for event_type in PaperEventType)}:
            raise ValueError("unknown event_type_filter")
        return normalized

    @staticmethod
    def _matches_event_type_scope(row: LocalPaperOperationAuditRow, scope: str) -> bool:
        return scope == "ALL" or row.event_type == scope

    @staticmethod
    def _instrument_scope(
        instrument_id_filter: str | None, rows: list[LocalPaperOperationAuditRow]
    ) -> str:
        if instrument_id_filter is None:
            return "ALL"
        normalized = instrument_id_filter.strip()
        if not normalized:
            raise ValueError("instrument_id_filter must not be blank")
        if normalized == "ALL":
            return normalized
        if normalized not in {row.instrument_id for row in rows}:
            raise ValueError("unknown instrument_id_filter")
        return normalized

    @staticmethod
    def _matches_instrument_scope(row: LocalPaperOperationAuditRow, scope: str) -> bool:
        return scope == "ALL" or row.instrument_id == scope

    @staticmethod
    def _time_window(
        start_time: datetime | None, end_time: datetime | None
    ) -> tuple[datetime | None, datetime | None]:
        for label, bound in (("start_time", start_time), ("end_time", end_time)):
            if bound is not None and (bound.tzinfo is None or bound.utcoffset() is None):
                raise ValueError(f"{label} must be timezone-aware")
        if start_time is not None and end_time is not None and start_time > end_time:
            raise ValueError("start_time must not be after end_time")
        return start_time, end_time

    @staticmethod
    def _matches_time_window(
        row: LocalPaperOperationAuditRow,
        window: tuple[datetime | None, datetime | None],
    ) -> bool:
        start_time, end_time = window
        return (
            (start_time is None or row.occurred_at >= start_time)
            and (end_time is None or row.occurred_at <= end_time)
        )

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
