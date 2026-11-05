import sqlite3

from app.db.connection import get_connection


def test_connection_creates_database(tmp_path):
    db_path = tmp_path / "test.db"

    with get_connection(db_path) as connection:
        result = connection.execute(
            "SELECT 1"
        ).fetchone()

        assert result[0] == 1

    assert db_path.exists()


def test_connection_enables_foreign_keys(tmp_path):
    db_path = tmp_path / "test.db"

    with get_connection(db_path) as connection:
        result = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()

        assert result[0] == 1


def test_connection_returns_rows_by_column_name(tmp_path):
    db_path = tmp_path / "test.db"

    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT 42 AS answer"
        ).fetchone()

        assert row["answer"] == 42