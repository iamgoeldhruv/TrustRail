
import sqlite3
from pathlib import Path

import pytest

from app.db.connection import get_connection
from app.txn.states import TransactionState
from app.txn.store import TransactionStore


def test_status_update_creates_ledger_event(database: Path):
    store = TransactionStore(database)

    updated = store.update_transaction_status(
        "txn-001",
        TransactionState.VALIDATING,
    )

    assert updated.status == TransactionState.VALIDATING

    events = store.ledger_store.get_events("txn-001")

    assert len(events) == 1
    assert events[0].type == "TRANSACTION_STATUS_CHANGED"
    assert events[0].payload == {
        "from_status": "PROPOSED",
        "to_status": "VALIDATING",
    }


def test_status_update_rolls_back_when_ledger_append_fails(
    database: Path,
):
    store = TransactionStore(database)

    with get_connection(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_ledger_insert
            BEFORE INSERT ON events
            BEGIN
                SELECT RAISE(ABORT, 'forced ledger failure');
            END;
            """
        )
        connection.commit()

    with pytest.raises(sqlite3.IntegrityError):
        store.update_transaction_status(
            "txn-001",
            TransactionState.VALIDATING,
        )

    with get_connection(database) as connection:
        row = connection.execute(
            "SELECT status FROM transactions WHERE id = ?",
            ("txn-001",),
        ).fetchone()

        event_count = connection.execute(
            "SELECT COUNT(*) FROM events WHERE txn_id = ?",
            ("txn-001",),
        ).fetchone()[0]

    assert row["status"] == "PROPOSED"
    assert event_count == 0


def test_claim_for_dispatch_creates_ledger_event(database: Path):
    # Set up a valid PRECHECK transaction.
    with get_connection(database) as connection:
        connection.execute(
            """
            UPDATE transactions
            SET status = ?
            WHERE id = ?
            """,
            ("PRECHECK", "txn-001"),
        )
        connection.commit()

    store = TransactionStore(database)

    claimed = store.claim_for_dispatch("txn-001")

    assert claimed is True

    transaction = store.get_transaction("txn-001")
    assert transaction.status == TransactionState.DISPATCHING

    events = store.ledger_store.get_events("txn-001")

    assert len(events) == 1
    assert events[0].payload["from_status"] == "PRECHECK"
    assert events[0].payload["to_status"] == "DISPATCHING"


def test_recovery_creates_ledger_event(database: Path):
    with get_connection(database) as connection:
        connection.execute(
            """
            UPDATE transactions
            SET status = ?
            WHERE id = ?
            """,
            ("DISPATCHING", "txn-001"),
        )
        connection.commit()

    store = TransactionStore(database)

    recovered_count = store.recover_on_start()

    assert recovered_count == 1

    transaction = store.get_transaction("txn-001")
    assert transaction.status == TransactionState.INDETERMINATE

    events = store.ledger_store.get_events("txn-001")

    assert len(events) == 1
    assert events[0].payload["from_status"] == "DISPATCHING"
    assert events[0].payload["to_status"] == "INDETERMINATE"
