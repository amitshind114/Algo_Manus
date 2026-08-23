"""Post-sync availability assessment for snapshot-pinned research universes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from algo_manus.domain.instruments import InstrumentMasterSnapshot, InstrumentStatus
from algo_manus.domain.universe import ResearchUniverse


class UniverseInstrumentState(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MISSING = "MISSING"
    MAPPING_CHANGED = "MAPPING_CHANGED"


@dataclass(frozen=True, slots=True)
class UniverseInstrumentAvailability:
    instrument_id: str
    state: UniverseInstrumentState
    reason: str


@dataclass(frozen=True, slots=True)
class UniverseAvailabilityReport:
    universe_id: str
    baseline_snapshot_id: str
    current_snapshot_id: str
    instruments: tuple[UniverseInstrumentAvailability, ...]

    @property
    def is_fully_active(self) -> bool:
        return all(item.state is UniverseInstrumentState.ACTIVE for item in self.instruments)


class UniverseAvailabilityService:
    """Compares a selected universe to a newer broker-master snapshot.

    A token replacement cannot be inferred safely from a display name alone.
    Such mappings remain missing and require explicit user review rather than an
    automatic remap to a superficially similar security.
    """

    def assess(
        self,
        *,
        universe: ResearchUniverse,
        baseline_snapshot: InstrumentMasterSnapshot,
        current_snapshot: InstrumentMasterSnapshot,
    ) -> UniverseAvailabilityReport:
        if universe.snapshot_id != baseline_snapshot.snapshot_id:
            raise ValueError("universe must be assessed against its pinned baseline snapshot")
        baseline_by_id = {instrument.instrument_id: instrument for instrument in baseline_snapshot.instruments}
        current_by_id = {instrument.instrument_id: instrument for instrument in current_snapshot.instruments}
        assessments: list[UniverseInstrumentAvailability] = []

        for instrument_id in universe.instrument_ids:
            baseline = baseline_by_id[instrument_id]
            current = current_by_id.get(instrument_id)
            if current is None:
                assessments.append(
                    UniverseInstrumentAvailability(
                        instrument_id=instrument_id,
                        state=UniverseInstrumentState.MISSING,
                        reason="absent from current broker master; explicit mapping review required",
                    )
                )
            elif current.status is not InstrumentStatus.ACTIVE:
                assessments.append(
                    UniverseInstrumentAvailability(
                        instrument_id=instrument_id,
                        state=UniverseInstrumentState.INACTIVE,
                        reason=f"current broker status is {current.status.value}",
                    )
                )
            elif (
                current.trading_symbol != baseline.trading_symbol
                or current.display_name != baseline.display_name
            ):
                assessments.append(
                    UniverseInstrumentAvailability(
                        instrument_id=instrument_id,
                        state=UniverseInstrumentState.MAPPING_CHANGED,
                        reason="broker symbol or display name changed; review before new research or paper use",
                    )
                )
            else:
                assessments.append(
                    UniverseInstrumentAvailability(
                        instrument_id=instrument_id,
                        state=UniverseInstrumentState.ACTIVE,
                        reason="active and unchanged in current broker master",
                    )
                )

        return UniverseAvailabilityReport(
            universe_id=universe.universe_id,
            baseline_snapshot_id=baseline_snapshot.snapshot_id,
            current_snapshot_id=current_snapshot.snapshot_id,
            instruments=tuple(assessments),
        )
