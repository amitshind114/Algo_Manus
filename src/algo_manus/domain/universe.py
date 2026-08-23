"""Selected research-universe contracts pinned to a broker-master snapshot."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResearchUniverse:
    """A user-labelled selection of resolved instrument identities.

    Storing the master snapshot ID makes later research experiments reproducible
    even if a security is renamed, removed or its broker token changes.
    """

    universe_id: str
    name: str
    snapshot_id: str
    instrument_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.universe_id.strip() or not self.name.strip() or not self.snapshot_id.strip():
            raise ValueError("universe_id, name and snapshot_id are required")
        if not self.instrument_ids:
            raise ValueError("a research universe requires at least one instrument")
        if len(set(self.instrument_ids)) != len(self.instrument_ids):
            raise ValueError("a research universe cannot contain duplicate instrument identities")
