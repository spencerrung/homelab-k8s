import sqlite3
from pathlib import Path
import tempfile
import unittest

from backup_state import backup


class BackupTests(unittest.TestCase):
    def test_snapshot_preserves_source_and_records(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "state.sqlite3"
            target = Path(directory) / "backup.sqlite3"
            with sqlite3.connect(source) as db:
                db.execute("CREATE TABLE history (id INTEGER PRIMARY KEY)")
                db.execute("INSERT INTO history VALUES (1)")
            original = source.read_bytes()
            backup(source, target)
            self.assertEqual(source.read_bytes(), original)
            with sqlite3.connect(target) as db:
                self.assertEqual(db.execute("SELECT id FROM history").fetchall(), [(1,)])
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone(), ("ok",))

    def test_missing_source_preserves_previous_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "missing.sqlite3"
            target = Path(directory) / "backup.sqlite3"
            target.write_bytes(b"previous snapshot")
            with self.assertRaises(sqlite3.OperationalError):
                backup(source, target)
            self.assertFalse(source.exists())
            self.assertEqual(target.read_bytes(), b"previous snapshot")
            self.assertFalse(target.with_suffix(".sqlite3.tmp").exists())
