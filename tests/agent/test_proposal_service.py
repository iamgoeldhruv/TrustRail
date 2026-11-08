
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from app.agent.proposal_service import (
    ProposalService,
    ProposalServiceError,
)
from app.db.connection import get_connection
from app.db.migrations import run_migrations
from app.ledger.canonical import canonical_json
from app.txn.states import TransactionState
from app.txn.store import TransactionStore


REPOSITORY = "iamgoeldhruv/LimeDraw"
RUN_ID = "run-proposal-test"
POLICY_ID = "policy-proposal-test"

VALID_POLICY = {
    "version": 1,
    "repo": REPOSITORY,
    "actions": {
        "close_issue": {
            "allowed": True,
            "conditions": {
                "inactive_days_gte": 30,
                "priority_not_in": ["P0", "P1"],
                "require_priority_label": True,
            },
            "requires_approval": True,
        }
    },
    "limits": {"max_actions_per_run": 3},
    "audit": {"enabled": True},
}


@pytest.fixture
def proposal_context(tmp_path):
    db_path = tmp_path / "proposal-test.db"
    run_migrations(db_path=db_path)

    now = datetime.now(UTC).isoformat()

    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO policies (
                id, version, nl_text, json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                POLICY_ID,
                1,
                "Close inactive low-priority issues",
                json.dumps(VALID_POLICY),
                "ACTIVE",
                now,
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
                RUN_ID,
                POLICY_ID,
                "Close eligible inactive issues",
                "test-model",
                now,
            ),
        )

        connection.commit()

    store = TransactionStore(db_path=db_path)

    service = ProposalService(
        store=store,
        expected_repository=REPOSITORY,
        db_path=db_path,
    )

    return {
        "db_path": db_path,
        "store": store,
        "service": service,
    }


def test_create_close_proposal_persists_proposed_transaction(
    proposal_context,
):
    service = proposal_context["service"]
    store = proposal_context["store"]

    transaction = service.create_close_proposal(
        run_id=RUN_ID,
        issue_number=42,
        reason="This issue has been inactive for over 30 days.",
    )

    assert transaction.status == TransactionState.PROPOSED
    assert transaction.run_id == RUN_ID
    assert transaction.policy_id == POLICY_ID
    assert transaction.policy_version == 1
    assert transaction.tool == "close_issue_with_note"

    persisted = store.get_transaction(transaction.id)

    assert persisted is not None
    assert persisted.status == TransactionState.PROPOSED
    assert persisted.id == transaction.id


def test_proposal_contains_exact_write_arguments(proposal_context):
    service = proposal_context["service"]

    transaction = service.create_close_proposal(
        run_id=RUN_ID,
        issue_number=42,
        reason="Close because it is inactive.",
    )

    assert transaction.args == {
        "issue_number": 42,
        "note": "Close because it is inactive.",
        "txn_id": transaction.id,
    }


def test_proposal_arguments_hash_matches_canonical_json(
    proposal_context,
):
    service = proposal_context["service"]

    transaction = service.create_close_proposal(
        run_id=RUN_ID,
        issue_number=42,
        reason="Close because it is inactive.",
    )

    expected_hash = hashlib.sha256(
        canonical_json(transaction.args).encode("utf-8")
    ).hexdigest()

    assert transaction.args_hash == expected_hash


@pytest.mark.parametrize(
    ("issue_number", "reason"),
    [
        (0, "Invalid issue number"),
        (-1, "Invalid issue number"),
        (True, "Boolean is not a valid issue number"),
        (42, ""),
        (42, "   "),
    ],
)
def test_invalid_arguments_are_rejected(
    proposal_context,
    issue_number,
    reason,
):
    service = proposal_context["service"]

    with pytest.raises(ProposalServiceError):
        service.create_close_proposal(
            run_id=RUN_ID,
            issue_number=issue_number,
            reason=reason,
        )


def test_missing_run_is_rejected(proposal_context):
    service = proposal_context["service"]

    with pytest.raises(ProposalServiceError, match="Run does not exist"):
        service.create_close_proposal(
            run_id="missing-run",
            issue_number=42,
            reason="Close inactive issue.",
        )


def test_empty_run_id_is_rejected(proposal_context):
    service = proposal_context["service"]

    with pytest.raises(ProposalServiceError, match="run_id"):
        service.create_close_proposal(
            run_id=" ",
            issue_number=42,
            reason="Close inactive issue.",
        )


def test_inactive_policy_is_rejected(proposal_context):
    db_path = proposal_context["db_path"]
    service = proposal_context["service"]

    with get_connection(db_path) as connection:
        connection.execute(
            "UPDATE policies SET status = 'INACTIVE' WHERE id = ?",
            (POLICY_ID,),
        )
        connection.commit()

    with pytest.raises(ProposalServiceError, match="active policy"):
        service.create_close_proposal(
            run_id=RUN_ID,
            issue_number=42,
            reason="Close inactive issue.",
        )


def test_policy_for_wrong_repository_is_rejected(tmp_path):
    db_path = tmp_path / "wrong-repo.db"
    run_migrations(db_path=db_path)

    now = datetime.now(UTC).isoformat()

    wrong_policy = {
        **VALID_POLICY,
        "repo": "another-owner/another-repo",
    }

    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO policies (
                id, version, nl_text, json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                POLICY_ID,
                1,
                "Wrong repository",
                json.dumps(wrong_policy),
                "ACTIVE",
                now,
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
                RUN_ID,
                POLICY_ID,
                "Test request",
                None,
                now,
            ),
        )
        connection.commit()

    service = ProposalService(
        store=TransactionStore(db_path=db_path),
        expected_repository=REPOSITORY,
        db_path=db_path,
    )

    with pytest.raises(ProposalServiceError, match="repository"):
        service.create_close_proposal(
            run_id=RUN_ID,
            issue_number=42,
            reason="Close inactive issue.",
        )


def test_semantically_invalid_policy_is_rejected(tmp_path):
    db_path = tmp_path / "invalid-policy.db"
    run_migrations(db_path=db_path)

    now = datetime.now(UTC).isoformat()

    invalid_policy = {
        **VALID_POLICY,
        "actions": {
            "close_issue": {
                "allowed": False,
                "conditions": VALID_POLICY["actions"]["close_issue"][
                    "conditions"
                ],
                "requires_approval": True,
            }
        },
    }

    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO policies (
                id, version, nl_text, json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                POLICY_ID,
                1,
                "Invalid policy",
                json.dumps(invalid_policy),
                "ACTIVE",
                now,
            ),
        )

        connection.execute(
            """
            INSERT INTO runs (
                id, policy_id, user_request, planner_model, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (RUN_ID, POLICY_ID, "Test request", None, now),
        )
        connection.commit()

    service = ProposalService(
        store=TransactionStore(db_path=db_path),
        expected_repository=REPOSITORY,
        db_path=db_path,
    )

    with pytest.raises(ProposalServiceError, match="policy is invalid"):
        service.create_close_proposal(
            run_id=RUN_ID,
            issue_number=42,
            reason="Close inactive issue.",
        )


def test_proposal_creation_does_not_change_transaction_to_dispatching(
    proposal_context,
):
    service = proposal_context["service"]
    store = proposal_context["store"]

    transaction = service.create_close_proposal(
        run_id=RUN_ID,
        issue_number=42,
        reason="Close inactive issue.",
    )

    transactions = store.list_transactions(run_id=RUN_ID)

    assert len(transactions) == 0 or all(
        item.status != TransactionState.DISPATCHING
        for item in transactions
    )

    persisted = store.get_transaction(transaction.id)
    assert persisted is not None
    assert persisted.status == TransactionState.PROPOSED
