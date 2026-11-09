
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from app.db.connection import get_connection
from app.db.migrations import run_migrations
from app.txn.models import TransactionCreate
from app.txn.states import TransactionState
from app.txn.store import TransactionStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test.db"

    run_migrations(db_path=db_path)

    return TransactionStore(db_path=db_path)


@pytest.fixture
def create_transaction(store):
    def _create(status=TransactionState.PRECHECK):
        # Create parent records required by foreign keys.
        with get_connection(store.db_path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO policies (
                    id, version, nl_text, json, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "policy-1",
                    1,
                    "Allow issue updates",
                    "{}",
                    "ACTIVE",
                    datetime.now(UTC).isoformat(),
                ),
            )

            connection.execute(
                """
                INSERT OR IGNORE INTO runs (
                    id, policy_id, user_request, planner_model, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "run-1",
                    "policy-1",
                    "Update GitHub issue",
                    "test-model",
                    datetime.now(UTC).isoformat(),
                ),
            )

            # Persist parent records before creating the transaction.
            connection.commit()

        transaction = TransactionCreate(
            run_id="run-1",
            policy_id="policy-1",
            policy_version=1,
            tool="github.update_issue",
            args={"issue_number": 123, "status": "closed"},
            args_hash="test-hash",
            status=status,
        )

        return store.create_transaction(transaction)

    return _create


def test_claim_for_dispatch_success(store, create_transaction):
    transaction = create_transaction()

    claimed = store.claim_for_dispatch(transaction.id)

    assert claimed is True

    updated = store.get_transaction(transaction.id)

    assert updated is not None
    assert updated.status == TransactionState.DISPATCHING


def test_claim_for_dispatch_repeated_claim_fails(
    store,
    create_transaction,
):
    transaction = create_transaction()

    first_claim = store.claim_for_dispatch(transaction.id)
    second_claim = store.claim_for_dispatch(transaction.id)

    assert first_claim is True
    assert second_claim is False


@pytest.mark.parametrize(
    "status",
    [
        TransactionState.APPROVED,
        TransactionState.SUCCEEDED,
        TransactionState.FAILED,
        TransactionState.DISPATCHING,
    ],
)
def test_claim_for_dispatch_rejects_ineligible_states(
    store,
    create_transaction,
    status,
):
    transaction = create_transaction(status=status)

    claimed = store.claim_for_dispatch(transaction.id)

    assert claimed is False

    updated = store.get_transaction(transaction.id)

    assert updated is not None
    assert updated.status == status


def test_claim_for_dispatch_nonexistent_transaction(store):
    claimed = store.claim_for_dispatch("nonexistent-id")

    assert claimed is False


def test_claim_for_dispatch_updates_timestamp(
    store,
    create_transaction,
):
    transaction = create_transaction()

    previous_timestamp = transaction.updated_at

    claimed = store.claim_for_dispatch(transaction.id)

    assert claimed is True

    claimed_transaction = store.get_transaction(transaction.id)

    assert claimed_transaction is not None
    assert claimed_transaction.updated_at >= previous_timestamp


def test_concurrent_claims_only_one_worker_succeeds(
    store,
    create_transaction,
):
    transaction = create_transaction()

    def claim():
        return store.claim_for_dispatch(transaction.id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: claim(), range(2)))

    assert results.count(True) == 1
    assert results.count(False) == 1

    updated = store.get_transaction(transaction.id)

    assert updated is not None
    assert updated.status == TransactionState.DISPATCHING


def test_recover_on_start_recovers_single_dispatching_transaction(
    store,
    create_transaction,
):
    transaction = create_transaction(
        status=TransactionState.DISPATCHING
    )

    recovered_count = store.recover_on_start()

    assert recovered_count == 1

    updated = store.get_transaction(transaction.id)

    assert updated is not None
    assert updated.status == TransactionState.INDETERMINATE


def test_recover_on_start_recovers_multiple_dispatching_transactions(
    store,
    create_transaction,
):
    first = create_transaction()
    second = create_transaction()

    store.claim_for_dispatch(first.id)
    store.claim_for_dispatch(second.id)

    recovered_count = store.recover_on_start()

    assert recovered_count == 2

    first_updated = store.get_transaction(first.id)
    second_updated = store.get_transaction(second.id)

    assert first_updated is not None
    assert second_updated is not None

    assert first_updated.status == TransactionState.INDETERMINATE
    assert second_updated.status == TransactionState.INDETERMINATE


def test_recover_on_start_does_not_modify_other_states(
    store,
    create_transaction,
):
    transaction = create_transaction(
        status=TransactionState.PRECHECK
    )

    recovered_count = store.recover_on_start()

    assert recovered_count == 0

    updated = store.get_transaction(transaction.id)

    assert updated is not None
    assert updated.status == TransactionState.PRECHECK


def test_recover_on_start_returns_zero_when_nothing_to_recover(
    store,
    create_transaction,
):
    create_transaction(status=TransactionState.SUCCEEDED)

    recovered_count = store.recover_on_start()

    assert recovered_count == 0


def test_recover_on_start_is_idempotent(
    store,
    create_transaction,
):
    transaction = create_transaction(
        status=TransactionState.DISPATCHING
    )

    first_recovery = store.recover_on_start()
    second_recovery = store.recover_on_start()

    assert first_recovery == 1
    assert second_recovery == 0

    updated = store.get_transaction(transaction.id)

    assert updated is not None
    assert updated.status == TransactionState.INDETERMINATE

def test_create_transaction_appends_initial_ledger_event(
    store,
    create_transaction,
):
    transaction = create_transaction()

    events = store.ledger_store.get_events(transaction.id)

    assert len(events) == 1

    event = events[0]

    assert event.type == "TRANSACTION_PROPOSED"
    assert event.txn_id == transaction.id
    assert event.seq == 1
    assert event.payload == {
        "run_id": transaction.run_id,
        "policy_id": transaction.policy_id,
        "policy_version": transaction.policy_version,
        "tool": transaction.tool,
        "initial_status": transaction.status.value,
    }

    verification = store.ledger_store.verify_chain(transaction.id)
    assert verification.valid is True


def test_create_transaction_rolls_back_if_ledger_append_fails(
    store,
    monkeypatch,
):
    # Create parent records required by the transaction foreign keys.
    with get_connection(store.db_path) as connection:
        now = datetime.now(UTC).isoformat()

        connection.execute(
            """
            INSERT INTO policies (
                id, version, nl_text, json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("rollback-policy", 1, "Test", "{}", "ACTIVE", now),
        )

        connection.execute(
            """
            INSERT INTO runs (
                id, policy_id, user_request, planner_model, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            ("rollback-run", "rollback-policy", "Test", None, now),
        )

        connection.commit()

    transaction = TransactionCreate(
        run_id="rollback-run",
        policy_id="rollback-policy",
        policy_version=1,
        tool="close_issue_with_note",
        args={"issue_number": 42},
        args_hash="test-hash",
        status=TransactionState.PROPOSED,
    )

    def fail_ledger_append(*args, **kwargs):
        raise RuntimeError("Simulated ledger failure")

    monkeypatch.setattr(
        store.ledger_store,
        "append_event_in_transaction",
        fail_ledger_append,
    )

    with pytest.raises(RuntimeError, match="Simulated ledger failure"):
        store.create_transaction(transaction)

    # The transaction insert must have been rolled back.
    assert store.get_transaction(transaction.id) is None

    # No ledger event should exist either.
    assert store.ledger_store.get_events(transaction.id) == []
