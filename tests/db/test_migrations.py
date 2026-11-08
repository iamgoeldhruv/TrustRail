
import sqlite3

import pytest

from app.db.connection import get_connection
from app.db.migrations import run_migrations


def test_migrations_are_applied(tmp_path):
    db_path = tmp_path / "test.db"

    # Use the actual migrations directory.
    from app.db.migrations import DEFAULT_MIGRATIONS_DIR

    applied = run_migrations(
        db_path=db_path,
        migrations_dir=DEFAULT_MIGRATIONS_DIR,
    )

    assert applied == [
        "001_initial_schema.sql",
        "002_transaction_indexes.sql",
        "003_events_append_only.sql",
        "004_authorization_decisions.sql",
    ]


def test_migrations_are_not_applied_twice(tmp_path):
    db_path = tmp_path / "test.db"

    from app.db.migrations import DEFAULT_MIGRATIONS_DIR

    first_run = run_migrations(
        db_path=db_path,
        migrations_dir=DEFAULT_MIGRATIONS_DIR,
    )

    second_run = run_migrations(
        db_path=db_path,
        migrations_dir=DEFAULT_MIGRATIONS_DIR,
    )

    assert len(first_run) == 4
    assert second_run == []


def test_migration_creates_expected_tables(tmp_path):
    db_path = tmp_path / "test.db"

    from app.db.migrations import DEFAULT_MIGRATIONS_DIR

    run_migrations(
        db_path=db_path,
        migrations_dir=DEFAULT_MIGRATIONS_DIR,
    )

    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

        table_names = {row["name"] for row in rows}

    expected_tables = {
        "policies",
        "runs",
        "transactions",
        "approvals",
        "events",
        "schema_migrations",
    }

    assert expected_tables.issubset(table_names)


def test_failed_migration_is_rolled_back(tmp_path):
    db_path = tmp_path / "test.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    (migrations_dir / "001_broken.sql").write_text(
        """
        CREATE TABLE temporary_table (id INTEGER PRIMARY KEY);
        INVALID SQL STATEMENT;
        """,
        encoding="utf-8",
    )

    with pytest.raises(sqlite3.Error):
        run_migrations(
            db_path=db_path,
            migrations_dir=migrations_dir,
        )

    with get_connection(db_path) as connection:
        result = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'temporary_table'
            """
        ).fetchone()

        migration = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            """
        ).fetchall()

    assert result is None
    assert migration == []
