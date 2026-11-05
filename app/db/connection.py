import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import settings


def _get_database_path(db_path: str | Path | None = None) -> Path:
    """Resolve the configured or explicitly provided database path."""
    return Path(db_path or settings.tr_db_path)


@contextmanager
def get_connection(
    db_path: str | Path | None = None,
) -> Iterator[sqlite3.Connection]:
    path = _get_database_path(db_path)

    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(path),
        timeout=30.0,
    )

    try:
        connection.row_factory = sqlite3.Row

        # Enable foreign key enforcement.
        connection.execute("PRAGMA foreign_keys = ON")

        # Wait up to 30 seconds if another connection holds a write lock.
        connection.execute("PRAGMA busy_timeout = 30000")

        yield connection

    finally:
        connection.close()