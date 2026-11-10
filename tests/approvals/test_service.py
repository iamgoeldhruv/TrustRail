
import json

import pytest

from app.approvals.hashing import approval_binding_hash
from app.approvals.models import ApprovalDecision
from app.approvals.service import ApprovalService
from app.approvals.store import ApprovalStore
from app.authz.models import Fact
from app.db.connection import get_connection
from app.txn.states import TransactionState
from app.txn.store import TransactionStore


FACTS = {
    "repository": "owner/repo",
    "issue_number": 1,
    "state": "open",
    "labels": [],
    "priority": "P2",
    "inactive_days": 45,
}

ARGS = {
    "issue_number": 1,
    "note": "demo",
    "txn_id": "txn-001",
}


def _prepare_pending_approval(
    database,
    *,
    facts=FACTS,
    server_revision="revision-1",
):
    with get_connection(database) as connection:
        connection.execute(
            """
            UPDATE transactions
            SET status = ?,
                authorization_decision = ?,
                facts_json = ?,
                server_revision = ?,
                tool = ?,
                args_json = ?
            WHERE id = ?
            """,
            (
                "PENDING_APPROVAL",
                "REQUIRES_APPROVAL",
                json.dumps(facts) if facts is not None else None,
                server_revision,
                "close_issue_with_note",
                json.dumps(ARGS),
                "txn-001",
            ),
        )
        connection.commit()


@pytest.fixture
def approval_service(database):
    transaction_store = TransactionStore(database)
    approval_store = ApprovalStore(database)

    return ApprovalService(transaction_store, approval_store)


def test_approve_records_correct_binding_hash(
    database,
    approval_service,
):
    _prepare_pending_approval(database)

    approval = approval_service.decide(
        txn_id="txn-001",
        approver="demo-operator",
        decision=ApprovalDecision.APPROVE,
    )

    expected_facts = Fact.model_validate(
        {
            key: FACTS[key]
            for key in (
                "issue_number",
                "state",
                "labels",
                "priority",
                "inactive_days",
            )
        }
    ).model_dump()

    expected_hash = approval_binding_hash(
        tool="close_issue_with_note",
        args=ARGS,
        policy_version=1,
        facts_that_matter=expected_facts,
        server_revision="revision-1",
    )

    assert approval.decision is ApprovalDecision.APPROVE
    assert approval.binding_hash == expected_hash

    transaction = TransactionStore(database).get_transaction("txn-001")

    assert transaction is not None
    assert transaction.status is TransactionState.APPROVED
    assert transaction.approval_id == approval.id


def test_reject_records_decision_and_transitions_transaction(
    database,
    approval_service,
):
    _prepare_pending_approval(database)

    approval = approval_service.decide(
        txn_id="txn-001",
        approver="demo-operator",
        decision=ApprovalDecision.REJECT,
    )

    assert approval.decision is ApprovalDecision.REJECT
    assert len(approval.binding_hash) == 64

    transaction = TransactionStore(database).get_transaction("txn-001")

    assert transaction is not None
    assert transaction.status is TransactionState.REJECTED
    assert transaction.approval_id == approval.id


def test_decision_rejected_when_transaction_is_not_pending(
    database,
    approval_service,
):
    with pytest.raises(ValueError, match="not awaiting approval"):
        approval_service.decide(
            txn_id="txn-001",
            approver="demo-operator",
            decision=ApprovalDecision.APPROVE,
        )


def test_decision_rejected_when_facts_are_missing(
    database,
    approval_service,
):
    _prepare_pending_approval(database, facts=None)

    with pytest.raises(ValueError, match="facts"):
        approval_service.decide(
            txn_id="txn-001",
            approver="demo-operator",
            decision=ApprovalDecision.APPROVE,
        )


def test_decision_rejected_when_facts_are_malformed(
    database,
    approval_service,
):
    _prepare_pending_approval(
        database,
        facts={"issue_number": "not-an-integer"},
    )

    with pytest.raises(ValueError, match="facts"):
        approval_service.decide(
            txn_id="txn-001",
            approver="demo-operator",
            decision=ApprovalDecision.APPROVE,
        )


def test_decision_rejected_when_server_revision_is_missing(
    database,
    approval_service,
):
    _prepare_pending_approval(database, server_revision=None)

    with pytest.raises(ValueError, match="server revision"):
        approval_service.decide(
            txn_id="txn-001",
            approver="demo-operator",
            decision=ApprovalDecision.APPROVE,
        )


def test_decision_rejected_for_blank_approver(
    database,
    approval_service,
):
    _prepare_pending_approval(database)

    with pytest.raises(ValueError, match="Approver"):
        approval_service.decide(
            txn_id="txn-001",
            approver="   ",
            decision=ApprovalDecision.APPROVE,
        )


def test_duplicate_decision_is_rejected(
    database,
    approval_service,
):
    _prepare_pending_approval(database)

    approval_service.decide(
        txn_id="txn-001",
        approver="demo-operator",
        decision=ApprovalDecision.APPROVE,
    )

    with pytest.raises(ValueError):
        approval_service.decide(
            txn_id="txn-001",
            approver="another-operator",
            decision=ApprovalDecision.APPROVE,
        )
