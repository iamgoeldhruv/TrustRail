
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
                INSERT INTO policies (
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
                INSERT INTO runs (
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
