"""Local immutable paper-event persistence."""

from .sqlite_ledger import SqlitePaperLedger

__all__ = ["SqlitePaperLedger"]
