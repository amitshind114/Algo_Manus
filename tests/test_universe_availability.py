from __future__ import annotations

import unittest

from algo_manus.application.instrument_sync import ResearchUniverseService
from algo_manus.application.universe_availability import (
    UniverseAvailabilityService,
    UniverseInstrumentState,
)
from algo_manus.domain.instruments import InstrumentStatus
from tests.fixtures import instrument, snapshot


class UniverseAvailabilityTests(unittest.TestCase):
    def test_changed_inactive_and_missing_instruments_require_review(self) -> None:
        baseline = snapshot()
        universe = ResearchUniverseService().create(
            universe_id="selected-equities",
            name="Selected equities",
            snapshot=baseline,
            selected_instrument_ids=(
                "ANGEL_ONE:NSE:NSE:500325",
                "ANGEL_ONE:NSE:NSE:532540",
            ),
        )
        changed = instrument(
            token="500325",
            symbol="RELIANCE-NEW-EQ",
            display_name="RELIANCE INDUSTRIES LIMITED",
        )
        current = snapshot(
            content=b"fixture-master-v2",
            instruments=(changed,),
        )

        report = UniverseAvailabilityService().assess(
            universe=universe,
            baseline_snapshot=baseline,
            current_snapshot=current,
        )

        states = {item.instrument_id: item.state for item in report.instruments}
        self.assertEqual(states["ANGEL_ONE:NSE:NSE:500325"], UniverseInstrumentState.MAPPING_CHANGED)
        self.assertEqual(states["ANGEL_ONE:NSE:NSE:532540"], UniverseInstrumentState.MISSING)
        self.assertFalse(report.is_fully_active)

    def test_inactive_broker_record_is_not_active(self) -> None:
        baseline = snapshot()
        universe = ResearchUniverseService().create(
            universe_id="single-equity",
            name="Single equity",
            snapshot=baseline,
            selected_instrument_ids=("ANGEL_ONE:NSE:NSE:500325",),
        )
        current = snapshot(
            content=b"fixture-master-v3",
            instruments=(
                instrument(
                    token="500325",
                    symbol="RELIANCE-EQ",
                    display_name="RELIANCE INDUSTRIES",
                    status=InstrumentStatus.INACTIVE,
                ),
            ),
        )

        report = UniverseAvailabilityService().assess(
            universe=universe,
            baseline_snapshot=baseline,
            current_snapshot=current,
        )

        self.assertEqual(report.instruments[0].state, UniverseInstrumentState.INACTIVE)


if __name__ == "__main__":
    unittest.main()
