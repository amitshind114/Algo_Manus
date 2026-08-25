from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


@contextmanager
def closed_sqlite_connection(database_path: Path) -> Iterator[sqlite3.Connection]:
    """Commit or roll back a test-side mutation and always release the Windows file handle."""

    connection = sqlite3.connect(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
