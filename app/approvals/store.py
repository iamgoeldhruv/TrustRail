from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.approvals.hashing import approval_binding_hash
from app.approvals.models import Approval, ApprovalCreate, ApprovalDecision
from app.db.connection import get_connection
from app.ledger.models import LedgerEventCreate
from app.ledger.store import LedgerStore


class ApprovalStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        self.ledger_store = LedgerStore(db_path)

    def create(self, approval: ApprovalCreate) -> Approval:
        with get_connection(self.db_path) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO approvals (
                        id, txn_id, approver, decision, binding_hash, policy_hash,
                        decided_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        approval.id,
                        approval.txn_id,
                        approval.approver,
                        approval.decision.value,
                        approval.binding_hash,
                        approval.policy_hash,
                        approval.decided_at.astimezone(UTC).isoformat(),
                    ),
                )
                connection.commit()
            except sqlite3.Error:
                connection.rollback()
                raise
        return Approval.model_validate(approval.model_dump())

    def record_decision(self, approval: ApprovalCreate) -> Approval:
        from app.txn.states import TransactionState
        from app.txn.transitions import transition
        """
        Atomically record an approval/rejection, attach it to its transaction,
        transition the transaction and append the audit event.
        """
        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    """
                    SELECT status, approval_id, authorization_decision
                    FROM transactions
                    WHERE id = ?
                    """,
                    (approval.txn_id,),
                ).fetchone()

                if row is None:
                    raise ValueError("Transaction does not exist")

                current_state = TransactionState(row["status"])

                if current_state is not TransactionState.PENDING_APPROVAL:
                    raise ValueError(
                        f"Transaction in state {current_state.value} "
                        "is not awaiting approval"
                    )

                if row["authorization_decision"] != "REQUIRES_APPROVAL":
                    raise ValueError(
                        "Transaction does not have an approval-required decision"
                    )

                if row["approval_id"] is not None:
                    raise ValueError("Transaction already has an attached approval")

                existing = connection.execute(
                    "SELECT id FROM approvals WHERE txn_id = ?",
                    (approval.txn_id,),
                ).fetchone()

                if existing is not None:
                    raise ValueError("An approval decision already exists")

                target_state = (
                    TransactionState.APPROVED
                    if approval.decision is ApprovalDecision.APPROVE
                    else TransactionState.REJECTED
                )

                next_state = transition(current_state, target_state)

                connection.execute(
                    """
                    INSERT INTO approvals (
                        id, txn_id, approver, decision, binding_hash, policy_hash,
                        decided_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        approval.id,
                        approval.txn_id,
                        approval.approver,
                        approval.decision.value,
                        approval.binding_hash,
                        approval.policy_hash,
                        approval.decided_at.astimezone(UTC).isoformat(),
                    ),
                )

                updated_at = datetime.now(UTC).isoformat()

                cursor = connection.execute(
                    """
                    UPDATE transactions
                    SET approval_id = ?,
                        status = ?,
                        updated_at = ?
                    WHERE id = ?
                    AND status = ?
                    AND approval_id IS NULL
                    """,
                    (
                        approval.id,
                        next_state.value,
                        updated_at,
                        approval.txn_id,
                        current_state.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise ValueError("Failed to attach approval to transaction")

                self.ledger_store.append_event_in_transaction(
                    connection,
                    LedgerEventCreate(
                        txn_id=approval.txn_id,
                        type="APPROVAL_DECISION_RECORDED",
                        payload={
                            "approval_id": approval.id,
                            "decision": approval.decision.value,
                            "approver": approval.approver,
                            "binding_hash": approval.binding_hash,
                            "policy_hash": approval.policy_hash,
                            "from_status": current_state.value,
                            "to_status": next_state.value,
                        },
                    ),
                )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        return Approval.model_validate(approval.model_dump())

    def get(self, approval_id: str) -> Approval | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
        if row is None:
            return None
        return Approval(
            id=row["id"],
            txn_id=row["txn_id"],
            approver=row["approver"],
            decision=ApprovalDecision(row["decision"]),
            binding_hash=row["binding_hash"],
            policy_hash=row["policy_hash"],
            decided_at=datetime.fromisoformat(row["decided_at"]),
        )

    def verify(
        self,
        *,
        approval_id: str,
        txn_id: str,
        tool: str,
        args: dict[str, Any],
        policy_version: int,
        facts_that_matter: dict[str, Any],
        server_revision: str,
        policy_hash: str | None = None,
    ) -> Approval:
        approval = self.get(approval_id)
        if approval is None:
            raise ValueError("Approval does not exist")
        if approval.txn_id != txn_id:
            raise ValueError("Approval is bound to a different transaction")
        if approval.decision is not ApprovalDecision.APPROVE:
            raise ValueError("Approval decision is not APPROVE")
        if policy_hash is not None and approval.policy_hash is None:
            raise ValueError("Approval has no policy hash")

        expected_hash = approval_binding_hash(
            tool=tool,
            args=args,
            policy_version=policy_version,
            facts_that_matter=facts_that_matter,
            server_revision=server_revision,
            policy_hash=policy_hash if policy_hash is not None else approval.policy_hash,
        )
        if approval.binding_hash != expected_hash:
            raise ValueError("Approval binding does not match the current action")
        return approval
