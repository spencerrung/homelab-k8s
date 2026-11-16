"""Create an atomic, consistent SQLite copy for Velero without writing to source."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys


def backup(source: Path, destination: Path) -> None:
    os.umask(0o077)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(temporary)) as dst:
                src.backup(dst)
                if dst.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise RuntimeError("SQLite backup integrity check failed")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    backup(Path(sys.argv[1]), Path(sys.argv[2]))
    print("SQLite backup integrity check passed")
