from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.db.connection import get_connection
from app.txn.exceptions import TransactionNotFoundError
from app.txn.models import Transaction, TransactionCreate
from app.txn.states import TransactionState
from app.txn.transitions import transition


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _row_to_transaction(row: sqlite3.Row) -> Transaction:
    try:
        return Transaction(
            id=row["id"],
            run_id=row["run_id"],
            policy_id=row["policy_id"],
            policy_version=row["policy_version"],
            tool=row["tool"],
            args=json.loads(row["args_json"]),
            args_hash=row["args_hash"],
            status=TransactionState(row["status"]),
            server_revision=row["server_revision"],
            facts=json.loads(row["facts_json"]) if row["facts_json"] is not None else None,
            approval_id=row["approval_id"],
            otari_request_ids=(
                json.loads(row["otari_request_ids_json"])
                if row["otari_request_ids_json"] is not None
                else None
            ),
            attempt=row["attempt"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid transaction data for {row['id']}") from exc


class TransactionStore:
    """SQLite persistence operations for transactions."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def create_transaction(self, transaction: TransactionCreate) -> Transaction:
        now = _utc_now()
        created_at = transaction.created_at or now
        updated_at = transaction.updated_at or created_at

        try:
            with get_connection(self.db_path) as connection:
                connection.execute(
                    """
                    INSERT INTO transactions (
                        id, run_id, policy_id, policy_version, tool, args_json,
                        args_hash, status, server_revision, facts_json, approval_id,
                        otari_request_ids_json, attempt, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(transaction.id),
                        transaction.run_id,
                        transaction.policy_id,
                        transaction.policy_version,
                        transaction.tool,
                        _json_dumps(transaction.args),
                        transaction.args_hash,
                        transaction.status.value,
                        transaction.server_revision,
                        _json_dumps(transaction.facts)
                        if transaction.facts is not None
                        else None,
                        transaction.approval_id,
                        _json_dumps(transaction.otari_request_ids)
                        if transaction.otari_request_ids is not None
                        else None,
                        transaction.attempt,
                        created_at.isoformat(),
                        updated_at.isoformat(),
                    ),
                )
                connection.commit()
        except sqlite3.Error:
            if "connection" in locals() and connection.in_transaction:
                connection.rollback()
            raise

        return Transaction(
            **transaction.model_dump(exclude={"created_at", "updated_at"}),
            created_at=created_at,
            updated_at=updated_at,
        )

    def get_transaction(self, transaction_id: UUID | str) -> Transaction | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM transactions WHERE id = ?",
                (str(transaction_id),),
            ).fetchone()
        return _row_to_transaction(row) if row is not None else None

    def update_transaction_status(
        self,
        transaction_id: UUID | str,
        target_state: TransactionState,
    ) -> Transaction:
        try:
            with get_connection(self.db_path) as connection:
                row = connection.execute(
                    "SELECT * FROM transactions WHERE id = ?",
                    (str(transaction_id),),
                ).fetchone()
                if row is None:
                    raise TransactionNotFoundError(transaction_id)

                current_state = TransactionState(row["status"])
                next_state = transition(current_state, target_state)
                updated_at = _utc_now().isoformat()
                connection.execute(
                    """
                    UPDATE transactions
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (next_state.value, updated_at, str(transaction_id)),
                )
                connection.commit()
        except sqlite3.Error:
            if "connection" in locals() and connection.in_transaction:
                connection.rollback()
            raise

        updated = self.get_transaction(transaction_id)
        if updated is None:
            raise TransactionNotFoundError(transaction_id)
        return updated

    def list_transactions(
        self,
        *,
        status: TransactionState | None = None,
        run_id: str | None = None,
    ) -> list[Transaction]:
        clauses: list[str] = []
        parameters: list[str] = []
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)
        if run_id is not None:
            clauses.append("run_id = ?")
            parameters.append(run_id)

        query = "SELECT * FROM transactions"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, id"

        with get_connection(self.db_path) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [_row_to_transaction(row) for row in rows]
