
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.approvals.hashing import approval_binding_hash, policy_content_hash
from app.approvals.models import Approval, ApprovalCreate, ApprovalDecision
from app.approvals.store import ApprovalStore
from app.db.connection import get_connection
from app.policy.models import Policy
from app.policy.validator import PolicySemanticError, validate_policy

if TYPE_CHECKING:
    from app.txn.store import TransactionStore


class ApprovalService:
    """Application service for recording transaction approval decisions."""

    def __init__(
        self,
        transaction_store: TransactionStore,
        approval_store: ApprovalStore,
    ) -> None:
        self.transaction_store = transaction_store
        self.approval_store = approval_store

    def decide(
        self,
        *,
        txn_id: str,
        approver: str,
        decision: ApprovalDecision,
    ) -> Approval:
        approver = approver.strip()
        if not approver:
            raise ValueError("Approver must not be empty")

        transaction = self.transaction_store.get_transaction(txn_id)

        if transaction is None:
            raise ValueError(f"Transaction {txn_id} does not exist")

        if transaction.status.value != "PENDING_APPROVAL":
            raise ValueError(
                f"Transaction in state {transaction.status.value} "
                "is not awaiting approval"
            )

        if transaction.authorization_decision != "REQUIRES_APPROVAL":
            raise ValueError(
                "Transaction does not have an approval-required decision"
            )

        if not isinstance(transaction.facts, dict):
            raise ValueError("Transaction has no valid persisted facts")

        if not transaction.server_revision:
            raise ValueError("Transaction has no server revision")

        # The evaluator stores repository alongside the Fact fields.
        # The executor hashes only the Fact fields, so reconstruct that
        # exact representation here.
        from app.authz.models import Fact

        fact_fields = (
            "issue_number",
            "state",
            "labels",
            "priority",
            "inactive_days",
        )

        try:
            facts_that_matter = Fact.model_validate(
                {
                    key: transaction.facts[key]
                    for key in fact_fields
                }
            ).model_dump()
        except (KeyError, ValueError) as exc:
            raise ValueError(
                "Persisted transaction facts are incomplete or invalid"
            ) from exc

        with get_connection(self.transaction_store.db_path) as connection:
            row = connection.execute(
                "SELECT json FROM policies WHERE id = ? AND version = ?",
                (transaction.policy_id, transaction.policy_version),
            ).fetchone()
        if row is None:
            raise ValueError("Policy version does not exist")
        raw_policy = json.loads(row["json"])
        try:
            policy = Policy.model_validate(raw_policy)
            validate_policy(policy)
            current_policy_hash = policy_content_hash(policy)
        except (ValueError, PolicySemanticError) as exc:
            if isinstance(raw_policy, dict):
                current_policy_hash = None
            else:
                raise ValueError("Stored policy is invalid") from exc

        binding_hash = approval_binding_hash(
            tool=transaction.tool,
            args=transaction.args,
            policy_version=transaction.policy_version,
            facts_that_matter=facts_that_matter,
            server_revision=transaction.server_revision,
            policy_hash=current_policy_hash,
        )

        approval = ApprovalCreate(
            txn_id=str(transaction.id),
            approver=approver,
            decision=decision,
            binding_hash=binding_hash,
            policy_hash=current_policy_hash,
            decided_at=datetime.now(UTC),
        )

        # This method atomically inserts the approval, attaches it,
        # transitions the transaction, and appends the ledger event.
        return self.approval_store.record_decision(approval)
