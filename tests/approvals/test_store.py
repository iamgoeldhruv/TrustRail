from datetime import UTC, datetime

import pytest

from app.approvals import (
    ApprovalCreate,
    ApprovalDecision,
    ApprovalStore,
    approval_binding_hash,
)


def _binding() -> dict:
    return {
        "tool": "close_issue_with_note",
        "args": {"issue_number": 1, "note": "demo", "txn_id": "txn-001"},
        "policy_version": 1,
        "facts_that_matter": {
            "issue_number": 1,
            "state": "open",
            "priority": "P2",
            "inactive_days": 45,
        },
        "server_revision": "revision-1",
    }


def test_approval_is_created_and_verified(database):
    store = ApprovalStore(database)
    binding = _binding()
    approval = store.create(
        ApprovalCreate(
            txn_id="txn-001",
            approver="operator",
            decision=ApprovalDecision.APPROVE,
            binding_hash=approval_binding_hash(**binding),
            decided_at=datetime.now(UTC),
        )
    )

    verified = store.verify(approval_id=approval.id, txn_id="txn-001", **binding)

    assert verified.id == approval.id
    assert verified.decision is ApprovalDecision.APPROVE


def test_rejected_approval_cannot_be_verified(database):
    store = ApprovalStore(database)
    binding = _binding()
    approval = store.create(
        ApprovalCreate(
            txn_id="txn-001",
            approver="operator",
            decision=ApprovalDecision.REJECT,
            binding_hash=approval_binding_hash(**binding),
            decided_at=datetime.now(UTC),
        )
    )

    with pytest.raises(ValueError, match="not APPROVE"):
        store.verify(approval_id=approval.id, txn_id="txn-001", **binding)


def test_changed_binding_cannot_be_verified(database):
    store = ApprovalStore(database)
    binding = _binding()
    approval = store.create(
        ApprovalCreate(
            txn_id="txn-001",
            approver="operator",
            decision=ApprovalDecision.APPROVE,
            binding_hash=approval_binding_hash(**binding),
            decided_at=datetime.now(UTC),
        )
    )

    changed = {**binding, "server_revision": "revision-2"}
    with pytest.raises(ValueError, match="binding"):
        store.verify(approval_id=approval.id, txn_id="txn-001", **changed)
