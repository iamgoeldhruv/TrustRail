
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.db.connection import get_connection
from app.db.migrations import run_migrations
from app.ledger.hashing import GENESIS_HASH
from app.ledger.models import LedgerEventCreate
from app.ledger.store import LedgerStore


@pytest.fixture
def database(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    _create_transaction(db_path, "txn-001")
    return db_path


def _create_transaction(db_path: Path, txn_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    policy_id = f"policy-{txn_id}"
    run_id = f"run-{txn_id}"
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO policies (
                id, version, nl_text, json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (policy_id, 1, "Test policy", "{}", "ACTIVE", now),
        )

        connection.execute(
            """
            INSERT INTO runs (
                id, policy_id, user_request, planner_model, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, policy_id, "Test request", None, now),
        )

        connection.execute(
            """
            INSERT INTO transactions (
                id, run_id, policy_id, policy_version,
                tool, args_json, args_hash, status,
                server_revision, facts_json, approval_id,
                otari_request_ids_json, attempt, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                txn_id,
                run_id,
                policy_id,
                1,
                "github.get_status",
                "{}",
                "test-args-hash",
                "PROPOSED",
                None,
                None,
                None,
                None,
                0,
                now,
                now,
            ),
        )

        connection.commit()


def _new_event(
    txn_id: str = "txn-001",
    event_type: str = "TRANSACTION_PROPOSED",
) -> LedgerEventCreate:
    return LedgerEventCreate(
        txn_id=txn_id,
        type=event_type,
        payload={"source": "test"},
    )


def test_append_first_event(database: Path):
    store = LedgerStore(database)

    event = store.append_event(_new_event())

    assert event.seq == 1
    assert event.prev_hash == GENESIS_HASH
    assert len(event.hash) == 64


def test_append_multiple_events(database: Path):
    store = LedgerStore(database)

    first = store.append_event(_new_event())
    second = store.append_event(
        _new_event(event_type="TRANSACTION_VALIDATED")
    )
    third = store.append_event(
        _new_event(event_type="TRANSACTION_APPROVED")
    )

    assert [first.seq, second.seq, third.seq] == [1, 2, 3]
    assert second.prev_hash == first.hash
    assert third.prev_hash == second.hash


def test_events_are_read_in_sequence_order(database: Path):
    store = LedgerStore(database)

    store.append_event(_new_event(event_type="EVENT_ONE"))
    store.append_event(_new_event(event_type="EVENT_TWO"))

    events = store.get_events("txn-001")

    assert [event.seq for event in events] == [1, 2]
    assert [event.type for event in events] == ["EVENT_ONE", "EVENT_TWO"]


def test_event_payload_is_persisted(database: Path):
    store = LedgerStore(database)

    original_payload = {
        "issue_number": 42,
        "metadata": {"source": "agent", "verified": True},
    }

    event = store.append_event(
        LedgerEventCreate(
            txn_id="txn-001",
            type="TRANSACTION_PROPOSED",
            payload=original_payload,
        )
    )

    persisted = store.get_events("txn-001")[0]

    assert persisted.id == event.id
    assert persisted.payload == original_payload


def test_different_transactions_have_independent_chains(database: Path):
    _create_transaction(database, "txn-002")
    store = LedgerStore(database)

    first = store.append_event(_new_event("txn-001"))
    second = store.append_event(_new_event("txn-002"))

    assert first.seq == 1
    assert second.seq == 1
    assert first.prev_hash == GENESIS_HASH
    assert second.prev_hash == GENESIS_HASH


def test_appending_to_unknown_transaction_fails(database: Path):
    store = LedgerStore(database)

    with pytest.raises(Exception):
        store.append_event(_new_event("missing-transaction"))

    assert store.get_events("missing-transaction") == []


def test_concurrent_appends_get_unique_sequences(database: Path):
    store = LedgerStore(database)

    def append_one(_: int) -> int:
        event = store.append_event(_new_event())
        return event.seq

    with ThreadPoolExecutor(max_workers=8) as executor:
        sequences = list(executor.map(append_one, range(20)))

    assert sorted(sequences) == list(range(1, 21))

    events = store.get_events("txn-001")
    assert len(events) == 20
    assert [event.seq for event in events] == list(range(1, 21))


def test_persisted_payload_is_valid_json(database: Path):
    store = LedgerStore(database)
    store.append_event(_new_event())

    with get_connection(database) as connection:
        row = connection.execute(
            "SELECT payload_json FROM events WHERE txn_id = ?",
            ("txn-001",),
        ).fetchone()

    assert json.loads(row["payload_json"]) == {"source": "test"}
