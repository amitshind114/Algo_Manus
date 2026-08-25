from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests.sqlite_test_utils import closed_sqlite_connection


class WindowsSqliteCleanupTests(unittest.TestCase):
    def test_test_mutation_connection_is_closed_before_temporary_cleanup(self) -> None:
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "temporary.sqlite3"
            with closed_sqlite_connection(database_path) as connection:
                connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
                connection.execute("INSERT INTO sample (value) VALUES (?)", ("saved",))

            with closed_sqlite_connection(database_path) as verification_connection:
                self.assertEqual(
                    verification_connection.execute("SELECT value FROM sample").fetchone()[0],
                    "saved",
                )

            database_path.unlink()
            self.assertFalse(database_path.exists())
