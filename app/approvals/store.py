from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.approvals.hashing import approval_binding_hash
from app.approvals.models import Approval, ApprovalCreate, ApprovalDecision
from app.db.connection import get_connection


class ApprovalStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def create(self, approval: ApprovalCreate) -> Approval:
        with get_connection(self.db_path) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO approvals (
                        id, txn_id, approver, decision, binding_hash, decided_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        approval.id,
                        approval.txn_id,
                        approval.approver,
                        approval.decision.value,
                        approval.binding_hash,
                        approval.decided_at.astimezone(UTC).isoformat(),
                    ),
                )
                connection.commit()
            except sqlite3.Error:
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
    ) -> Approval:
        approval = self.get(approval_id)
        if approval is None:
            raise ValueError("Approval does not exist")
        if approval.txn_id != txn_id:
            raise ValueError("Approval is bound to a different transaction")
        if approval.decision is not ApprovalDecision.APPROVE:
            raise ValueError("Approval decision is not APPROVE")

        expected_hash = approval_binding_hash(
            tool=tool,
            args=args,
            policy_version=policy_version,
            facts_that_matter=facts_that_matter,
            server_revision=server_revision,
        )
        if approval.binding_hash != expected_hash:
            raise ValueError("Approval binding does not match the current action")
        return approval
