
import sqlite3
from pathlib import Path

import pytest

from app.db.connection import get_connection
from app.ledger.store import LedgerStore


def test_event_update_is_rejected(database: Path, new_event):
    store = LedgerStore(database)
    store.append_event(new_event())

    with get_connection(database) as connection:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="ledger events are append-only",
        ):
            connection.execute(
                """
                UPDATE events
                SET type = ?
                WHERE txn_id = ? AND seq = 1
                """,
                ("TAMPERED_EVENT", "txn-001"),
            )


def test_event_delete_is_rejected(database: Path, new_event):
    store = LedgerStore(database)
    store.append_event(new_event())

    with get_connection(database) as connection:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="ledger events are append-only",
        ):
            connection.execute(
                """
                DELETE FROM events
                WHERE txn_id = ? AND seq = 1
                """,
                ("txn-001",),
            )


def test_event_insert_is_allowed(database: Path, new_event):
    store = LedgerStore(database)

    event = store.append_event(new_event())

    assert event.seq == 1
    assert len(store.get_events("txn-001")) == 1


def test_event_read_is_allowed(database: Path, new_event):
    store = LedgerStore(database)
    store.append_event(new_event())

    events = store.get_events("txn-001")

    assert len(events) == 1
    assert events[0].type == "TRANSACTION_PROPOSED"
