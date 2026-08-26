"""Display-safe local lifecycle projection for retained India-market instrument masters.

The service reads immutable normalized snapshots only.  It cannot download a
master, query prices, access an account, synchronize a broker, alter a
universe, or submit an order.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from algo_manus.domain.instruments import Instrument, InstrumentMasterSnapshot, InstrumentStatus


class InstrumentLifecycleState(StrEnum):
    """Local readiness interpretation for one retained canonical instrument record."""

    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"
    UNRESOLVED = "UNRESOLVED"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class IndiaInstrumentLifecycleRow:
    """Retained canonical contract metadata plus a local review/readiness interpretation."""

    instrument_id: str
    exchange: str
    segment: str
    trading_symbol: str
    display_name: str
    instrument_type: str
    broker_token: str
    broker_status: str
    expiry: object | None
    strike: float | None
    option_type: str | None
    lot_size: int | None
    tick_size: float | None
    contract_descriptor: str
    lifecycle_state: InstrumentLifecycleState
    review_required: bool
    review_reason: str | None


@dataclass(frozen=True, slots=True)
class IndiaInstrumentLifecycleSummary:
    snapshot_id: str
    baseline_snapshot_id: str | None
    retained_record_count: int
    ready_count: int
    review_required_count: int
    derivative_count: int
    segment_counts: Mapping[str, int]
    lifecycle_counts: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class IndiaInstrumentLifecycleProjection:
    """Read-only lifecycle interpretation of one retained current snapshot."""

    summary: IndiaInstrumentLifecycleSummary
    instruments: tuple[IndiaInstrumentLifecycleRow, ...]


class InstrumentLifecycleReadService:
    """Compare canonical retained snapshots without auto-remapping or changing them."""

    _CONTRACT_FIELDS = (
        "trading_symbol",
        "display_name",
        "instrument_type",
        "expiry",
        "strike",
        "option_type",
        "lot_size",
        "tick_size",
    )

    def project(
        self,
        current_snapshot: InstrumentMasterSnapshot,
        *,
        baseline_snapshot: InstrumentMasterSnapshot | None = None,
    ) -> IndiaInstrumentLifecycleProjection:
        """Project retained current/baseline snapshots into local review evidence.

        A canonical identity absent from the current snapshot is retained in the
        view as ``MISSING``.  It is never automatically remapped using a name,
        symbol, expiry or superficially similar contract.
        """

        if baseline_snapshot is not None and baseline_snapshot.broker.upper() != current_snapshot.broker.upper():
            raise ValueError("baseline and current snapshots must belong to the same broker")
        baseline_by_id = (
            {instrument.instrument_id: instrument for instrument in baseline_snapshot.instruments}
            if baseline_snapshot is not None
            else {}
        )
        current_by_id = {instrument.instrument_id: instrument for instrument in current_snapshot.instruments}
        rows = [
            self._current_row(instrument, baseline_by_id.get(instrument.instrument_id))
            for instrument in current_snapshot.instruments
        ]
        if baseline_snapshot is not None:
            rows.extend(
                self._missing_row(instrument)
                for instrument_id, instrument in baseline_by_id.items()
                if instrument_id not in current_by_id
            )
        ordered_rows = tuple(sorted(rows, key=lambda item: item.instrument_id))
        segment_counts = Counter(item.segment for item in ordered_rows)
        lifecycle_counts = Counter(item.lifecycle_state.value for item in ordered_rows)
        return IndiaInstrumentLifecycleProjection(
            summary=IndiaInstrumentLifecycleSummary(
                snapshot_id=current_snapshot.snapshot_id,
                baseline_snapshot_id=baseline_snapshot.snapshot_id if baseline_snapshot is not None else None,
                retained_record_count=len(ordered_rows),
                ready_count=sum(item.lifecycle_state is InstrumentLifecycleState.READY for item in ordered_rows),
                review_required_count=sum(item.review_required for item in ordered_rows),
                derivative_count=sum(self._is_derivative(item) for item in ordered_rows),
                segment_counts=self._frozen_counts(segment_counts),
                lifecycle_counts=self._frozen_counts(lifecycle_counts),
            ),
            instruments=ordered_rows,
        )

    def _current_row(
        self,
        instrument: Instrument,
        baseline: Instrument | None,
    ) -> IndiaInstrumentLifecycleRow:
        state, review_reason = self._status_state(instrument)
        if state is InstrumentLifecycleState.READY and baseline is not None:
            changed_fields = self._changed_fields(baseline, instrument)
            if changed_fields:
                state = InstrumentLifecycleState.REVIEW_REQUIRED
                review_reason = (
                    "canonical contract metadata changed: "
                    + ", ".join(changed_fields)
                    + "; review before new research or paper use"
                )
        return self._row(instrument, state, review_reason)

    @staticmethod
    def _status_state(instrument: Instrument) -> tuple[InstrumentLifecycleState, str | None]:
        if instrument.status is InstrumentStatus.ACTIVE:
            return InstrumentLifecycleState.READY, None
        state_by_status = {
            InstrumentStatus.INACTIVE: InstrumentLifecycleState.INACTIVE,
            InstrumentStatus.EXPIRED: InstrumentLifecycleState.EXPIRED,
            InstrumentStatus.UNRESOLVED: InstrumentLifecycleState.UNRESOLVED,
        }
        state = state_by_status[instrument.status]
        return state, f"current retained broker-master status is {instrument.status.value}; review required"

    def _missing_row(self, baseline: Instrument) -> IndiaInstrumentLifecycleRow:
        return self._row(
            baseline,
            InstrumentLifecycleState.MISSING,
            "absent from current retained broker master; explicit mapping review required",
        )

    @classmethod
    def _changed_fields(cls, baseline: Instrument, current: Instrument) -> tuple[str, ...]:
        return tuple(
            field
            for field in cls._CONTRACT_FIELDS
            if getattr(baseline, field) != getattr(current, field)
        )

    @staticmethod
    def _row(
        instrument: Instrument,
        lifecycle_state: InstrumentLifecycleState,
        review_reason: str | None,
    ) -> IndiaInstrumentLifecycleRow:
        return IndiaInstrumentLifecycleRow(
            instrument_id=instrument.instrument_id,
            exchange=instrument.exchange,
            segment=instrument.segment,
            trading_symbol=instrument.trading_symbol,
            display_name=instrument.display_name,
            instrument_type=instrument.instrument_type.value,
            broker_token=instrument.broker_token,
            broker_status=instrument.status.value,
            expiry=instrument.expiry,
            strike=instrument.strike,
            option_type=instrument.option_type.value if instrument.option_type is not None else None,
            lot_size=instrument.lot_size,
            tick_size=instrument.tick_size,
            contract_descriptor=instrument.contract_descriptor,
            lifecycle_state=lifecycle_state,
            review_required=lifecycle_state is not InstrumentLifecycleState.READY,
            review_reason=review_reason,
        )

    @staticmethod
    def _is_derivative(row: IndiaInstrumentLifecycleRow) -> bool:
        return row.instrument_type in {"FUTURE", "OPTION"}

    @staticmethod
    def _frozen_counts(counts: Counter[str]) -> Mapping[str, int]:
        return MappingProxyType(dict(sorted(counts.items())))
