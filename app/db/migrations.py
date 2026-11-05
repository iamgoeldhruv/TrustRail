import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.db.connection import get_connection


DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _create_migrations_table(connection: sqlite3.Connection) -> None:
    """Create the migration tracking table if it does not exist."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )

    connection.commit()


def _get_applied_migrations(
    connection: sqlite3.Connection,
) -> set[str]:
    """Return the names of migrations already applied."""

    rows = connection.execute("SELECT version FROM schema_migrations").fetchall()

    return {row["version"] for row in rows}


def _apply_migration(
    connection: sqlite3.Connection,
    migration_file: Path,
) -> None:
    """Apply one migration atomically and record its completion."""

    sql = migration_file.read_text(encoding="utf-8")
    migration_name = migration_file.name
    applied_at = datetime.now(timezone.utc).isoformat()

    try:
        connection.executescript(f"BEGIN IMMEDIATE;\n{sql}")

        connection.execute(
            """
            INSERT INTO schema_migrations (version, applied_at)
            VALUES (?, ?)
            """,
            (migration_name, applied_at),
        )

        connection.commit()

    except sqlite3.Error:
        if connection.in_transaction:
            connection.rollback()
        raise


def run_migrations(
    db_path: str | Path | None = None,
    migrations_dir: Path = DEFAULT_MIGRATIONS_DIR,
) -> list[str]:
    """
    Apply all pending SQL migrations in filename order.

    Returns the names of migrations applied during this invocation.
    """

    if not migrations_dir.is_dir():
        raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")

    migration_files = sorted(migrations_dir.glob("*.sql"))

    applied_migrations: list[str] = []

    with get_connection(db_path) as connection:
        _create_migrations_table(connection)

        existing_migrations = _get_applied_migrations(connection)

        for migration_file in migration_files:
            migration_name = migration_file.name

            if migration_name in existing_migrations:
                continue

            _apply_migration(connection, migration_file)

            applied_migrations.append(migration_name)

    return applied_migrations
