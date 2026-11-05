from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.db.connection import get_connection
from app.db.migrations import run_migrations
from app.ledger.models import LedgerEventCreate


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


@pytest.fixture
def database(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"

    run_migrations(db_path=db_path)
    _create_transaction(db_path, "txn-001")

    return db_path


@pytest.fixture
def new_event():
    def _new_event(
        txn_id: str = "txn-001",
        event_type: str = "TRANSACTION_PROPOSED",
    ) -> LedgerEventCreate:
        return LedgerEventCreate(
            txn_id=txn_id,
            type=event_type,
            payload={"source": "test"},
        )

    return _new_event