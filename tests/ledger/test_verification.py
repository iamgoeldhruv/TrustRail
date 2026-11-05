from pathlib import Path

from app.db.connection import get_connection
from app.ledger.store import LedgerStore
import sqlite3
import pytest
def _disable_append_only_triggers(connection: sqlite3.Connection) -> None:
    """Simulate privileged database access for tampering tests."""

    connection.execute("DROP TRIGGER IF EXISTS prevent_event_update")
    connection.execute("DROP TRIGGER IF EXISTS prevent_event_delete")


def test_verify_valid_chain(database: Path, new_event):
    store = LedgerStore(database)

    store.append_event(new_event(event_type="EVENT_ONE"))
    store.append_event(new_event(event_type="EVENT_TWO"))
    store.append_event(new_event(event_type="EVENT_THREE"))

    result = store.verify_chain("txn-001")

    assert result.valid is True
    assert result.events_checked == 3
    assert result.first_invalid_seq is None
    assert result.reason is None


def test_verify_empty_chain(database: Path):
    store = LedgerStore(database)

    result = store.verify_chain("txn-001")

    assert result.valid is True
    assert result.events_checked == 0
    assert result.first_invalid_seq is None


def test_detect_modified_payload(database: Path, new_event):
    store = LedgerStore(database)
    store.append_event(new_event())

    with get_connection(database) as connection:
        _disable_append_only_triggers(connection)
        connection.execute(
            """
            UPDATE events
            SET payload_json = ?
            WHERE txn_id = ? AND seq = 1
            """,
            ('{"source":"tampered"}', "txn-001"),
        )
        connection.commit()

    result = store.verify_chain("txn-001")

    assert result.valid is False
    assert result.first_invalid_seq == 1
    assert "hash" in result.reason.lower()


def test_detect_modified_hash(database: Path, new_event):
    store = LedgerStore(database)
    store.append_event(new_event())

    with get_connection(database) as connection:
        _disable_append_only_triggers(connection)
        connection.execute(
            """
            UPDATE events
            SET hash = ?
            WHERE txn_id = ? AND seq = 1
            """,
            ("a" * 64, "txn-001"),
        )
        connection.commit()

    result = store.verify_chain("txn-001")

    assert result.valid is False
    assert result.first_invalid_seq == 1


def test_detect_broken_previous_hash_link(database: Path, new_event):
    store = LedgerStore(database)
    store.append_event(new_event(event_type="EVENT_ONE"))
    store.append_event(new_event(event_type="EVENT_TWO"))

    with get_connection(database) as connection:
        _disable_append_only_triggers(connection)
        connection.execute(
            """
            UPDATE events
            SET prev_hash = ?
            WHERE txn_id = ? AND seq = 2
            """,
            ("b" * 64, "txn-001"),
        )
        connection.commit()

    result = store.verify_chain("txn-001")

    assert result.valid is False
    assert result.first_invalid_seq == 2
    assert "previous hash" in result.reason.lower()


def test_detect_missing_sequence(database: Path, new_event):
    store = LedgerStore(database)
    store.append_event(new_event(event_type="EVENT_ONE"))
    store.append_event(new_event(event_type="EVENT_TWO"))

    with get_connection(database) as connection:
        _disable_append_only_triggers(connection)
        connection.execute(
            """
            UPDATE events
            SET seq = 3
            WHERE txn_id = ? AND seq = 2
            """,
            ("txn-001",),
        )
        connection.commit()

    result = store.verify_chain("txn-001")

    assert result.valid is False
    assert result.first_invalid_seq == 2
    assert "sequence" in result.reason.lower()


def test_detect_invalid_genesis_pointer(database: Path, new_event):
    store = LedgerStore(database)
    store.append_event(new_event())

    with get_connection(database) as connection:
        _disable_append_only_triggers(connection)
        connection.execute(
            """
            UPDATE events
            SET prev_hash = ?
            WHERE txn_id = ? AND seq = 1
            """,
            ("c" * 64, "txn-001"),
        )
        connection.commit()

    result = store.verify_chain("txn-001")

    assert result.valid is False
    assert result.first_invalid_seq == 1


def test_detect_invalid_payload_json(database: Path, new_event):
    store = LedgerStore(database)
    store.append_event(new_event())

    with get_connection(database) as connection:
        _disable_append_only_triggers(connection)
        connection.execute(
            """
            UPDATE events
            SET payload_json = ?
            WHERE txn_id = ? AND seq = 1
            """,
            ("{invalid-json", "txn-001"),
        )
        connection.commit()

    result = store.verify_chain("txn-001")

    assert result.valid is False
    assert result.first_invalid_seq == 1
    assert "cannot be verified" in result.reason.lower()
