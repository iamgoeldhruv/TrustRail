
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.db.connection import get_connection
from app.ledger.models import LedgerEventCreate
from app.ledger.store import LedgerStore
from app.txn.exceptions import TransactionNotFoundError
from app.txn.models import Transaction, TransactionCreate
from app.txn.states import TransactionState
from app.txn.transitions import transition
from app.txn.exceptions import (
    ApprovalAlreadyAttachedError,
    InvalidTransitionError,
    TransactionNotFoundError,
)

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
            facts=(
                json.loads(row["facts_json"])
                if row["facts_json"] is not None
                else None
            ),
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
        raise ValueError(
            f"Invalid transaction data for {row['id']}"
        ) from exc


def _append_request_id_json(
    row: sqlite3.Row,
    request_id: str | None,
) -> str | None:
    """Append an Otari request ID without introducing duplicates."""
    raw_ids = row["otari_request_ids_json"]

    if raw_ids is None:
        request_ids: list[str] = []
    else:
        request_ids = json.loads(raw_ids)

    if not isinstance(request_ids, list):
        raise ValueError("Invalid Otari request ID data")

    if request_id and request_id not in request_ids:
        request_ids.append(request_id)

    return _json_dumps(request_ids) if request_ids else None


class TransactionStore:
    """SQLite persistence operations for transactions."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        self.ledger_store = LedgerStore(db_path)

    def create_transaction(
        self,
        transaction: TransactionCreate,
    ) -> Transaction:
        now = _utc_now()
        created_at = transaction.created_at or now
        updated_at = transaction.updated_at or created_at

        with get_connection(self.db_path) as connection:
            try:
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
                        (
                            _json_dumps(transaction.facts)
                            if transaction.facts is not None
                            else None
                        ),
                        transaction.approval_id,
                        (
                            _json_dumps(transaction.otari_request_ids)
                            if transaction.otari_request_ids is not None
                            else None
                        ),
                        transaction.attempt,
                        created_at.isoformat(),
                        updated_at.isoformat(),
                    ),
                )

                connection.commit()

            except sqlite3.Error:
                connection.rollback()
                raise

        return Transaction(
            **transaction.model_dump(
                exclude={"created_at", "updated_at"}
            ),
            created_at=created_at,
            updated_at=updated_at,
        )

    def get_transaction(
        self,
        transaction_id: UUID | str,
    ) -> Transaction | None:
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
        """
        Update transaction status and append its ledger event atomically.

        If either the status update or ledger append fails, both are rolled back.
        """
        transaction_id = str(transaction_id)

        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    "SELECT * FROM transactions WHERE id = ?",
                    (transaction_id,),
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
                    (next_state.value, updated_at, transaction_id),
                )

                self.ledger_store.append_event_in_transaction(
                    connection,
                    LedgerEventCreate(
                        txn_id=transaction_id,
                        type="TRANSACTION_STATUS_CHANGED",
                        payload={
                            "from_status": current_state.value,
                            "to_status": next_state.value,
                        },
                    ),
                )

                connection.commit()

            except Exception:
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

    def record_otari_request_id(
        self,
        transaction_id: UUID | str,
        request_id: str | None,
    ) -> None:
        """Persist an Otari request ID without changing transaction state."""
        if not request_id:
            return

        transaction_id = str(transaction_id)
        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM transactions WHERE id = ?",
                    (transaction_id,),
                ).fetchone()
                if row is None:
                    raise TransactionNotFoundError(transaction_id)

                connection.execute(
                    """
                    UPDATE transactions
                    SET otari_request_ids_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        _append_request_id_json(row, request_id),
                        _utc_now().isoformat(),
                        transaction_id,
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def attach_approval(
    self,
    transaction_id: UUID | str,
    approval_id: str,
) -> None:
        """Attach an approval once; repeated attachment of the same ID is safe."""
        transaction_id = str(transaction_id)

        if not approval_id or not approval_id.strip():
            raise ValueError("approval_id must not be empty")

        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    """
                    SELECT approval_id
                    FROM transactions
                    WHERE id = ?
                    """,
                    (transaction_id,),
                ).fetchone()

                if row is None:
                    raise TransactionNotFoundError(transaction_id)

                existing_approval_id = row["approval_id"]

                if existing_approval_id == approval_id:
                    connection.commit()
                    return

                if existing_approval_id is not None:
                    raise ApprovalAlreadyAttachedError(
                        transaction_id=transaction_id,
                        existing_approval_id=existing_approval_id,
                        attempted_approval_id=approval_id,
                    )

                connection.execute(
                    """
                    UPDATE transactions
                    SET approval_id = ?, updated_at = ?
                    WHERE id = ?
                    AND approval_id IS NULL
                    """,
                    (approval_id, _utc_now().isoformat(), transaction_id),
                )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

    def claim_for_dispatch(
        self,
        transaction_id: UUID | str,
    ) -> bool:
        """
        Atomically claim a PRECHECK transaction for dispatch.

        The state transition and ledger event are committed together.

        Returns True if claimed, False if the transaction does not exist
        or is not in PRECHECK.
        """
        transaction_id = str(transaction_id)

        expected_state = TransactionState.PRECHECK
        target_state = transition(
            expected_state,
            TransactionState.DISPATCHING,
        )

        updated_at = _utc_now().isoformat()

        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                cursor = connection.execute(
                    """
                    UPDATE transactions
                    SET status = ?,
                        updated_at = ?
                    WHERE id = ?
                    AND status = ?
                    """,
                    (
                        target_state.value,
                        updated_at,
                        transaction_id,
                        expected_state.value,
                    ),
                )

                claimed = cursor.rowcount == 1

                if claimed:
                    self.ledger_store.append_event_in_transaction(
                        connection,
                        LedgerEventCreate(
                            txn_id=transaction_id,
                            type="TRANSACTION_STATUS_CHANGED",
                            payload={
                                "from_status": expected_state.value,
                                "to_status": target_state.value,
                                "reason": "dispatch_claimed",
                            },
                        ),
                    )

                connection.commit()
                return claimed

            except Exception:
                connection.rollback()
                raise

    
    def recover_on_start(self) -> int:
        

        recoverable_states = (
            TransactionState.DISPATCHING,
            TransactionState.RECONCILING,
        )

        target_state = TransactionState.INDETERMINATE
        updated_at = _utc_now().isoformat()

        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                placeholders = ", ".join("?" for _ in recoverable_states)

                rows = connection.execute(
                    f"""
                    SELECT id, status
                    FROM transactions
                    WHERE status IN ({placeholders})
                    ORDER BY id
                    """,
                    tuple(state.value for state in recoverable_states),
                ).fetchall()

                for row in rows:
                    transaction_id = row["id"]
                    previous_state = TransactionState(row["status"])

                    # Validate the transition using the central state machine.
                    validated_target = transition(
                        previous_state,
                        target_state,
                    )

                    cursor = connection.execute(
                        """
                        UPDATE transactions
                        SET status = ?, updated_at = ?
                        WHERE id = ? AND status = ?
                        """,
                        (
                            validated_target.value,
                            updated_at,
                            transaction_id,
                            previous_state.value,
                        ),
                    )

                    # Never append a recovery event unless the status update
                    # actually succeeded.
                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            f"Failed to recover transaction {transaction_id}: "
                            "status changed unexpectedly"
                        )

                    self.ledger_store.append_event_in_transaction(
                        connection,
                        LedgerEventCreate(
                            txn_id=transaction_id,
                            type="TRANSACTION_STATUS_CHANGED",
                            payload={
                                "from_status": previous_state.value,
                                "to_status": validated_target.value,
                                "reason": "startup_recovery",
                            },
                        ),
                    )

                connection.commit()

                return len(rows)

            except Exception:
                connection.rollback()
                raise


    def claim_for_reconciliation(
        self,
        transaction_id: UUID | str,
    ) -> TransactionState | None:
        """
        Atomically claim an INDETERMINATE or UNRESOLVED transaction.

        Returns the original state if successfully claimed.
        Returns None if the transaction does not exist or cannot be claimed.
        """
        transaction_id = str(transaction_id)

        eligible_states = {
            TransactionState.INDETERMINATE,
            TransactionState.UNRESOLVED,
        }

        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    "SELECT status FROM transactions WHERE id = ?",
                    (transaction_id,),
                ).fetchone()

                if row is None:
                    connection.commit()
                    return None

                original_state = TransactionState(row["status"])

                if original_state not in eligible_states:
                    connection.commit()
                    return None

                target_state = transition(
                    original_state,
                    TransactionState.RECONCILING,
                )

                updated_at = _utc_now().isoformat()

                cursor = connection.execute(
                    """
                    UPDATE transactions
                    SET status = ?, updated_at = ?
                    WHERE id = ? AND status = ?
                    """,
                    (
                        target_state.value,
                        updated_at,
                        transaction_id,
                        original_state.value,
                    ),
                )

                if cursor.rowcount != 1:
                    connection.rollback()
                    return None

                self.ledger_store.append_event_in_transaction(
                    connection,
                    LedgerEventCreate(
                        txn_id=transaction_id,
                        type="TRANSACTION_STATUS_CHANGED",
                        payload={
                            "from_status": original_state.value,
                            "to_status": target_state.value,
                            "reason": "reconciliation_claimed",
                        },
                    ),
                )

                connection.commit()
                return original_state

            except Exception:
                connection.rollback()
                raise

    def complete_reconciliation(
        self,
        transaction_id: UUID | str,
        target_state: TransactionState,
        *,
        evidence: dict[str, Any],
        reason: str,
        otari_request_id: str | None = None,
    ) -> Transaction:
        """
        Atomically persist reconciliation evidence and its final outcome.

        Updates transaction status, stores the Otari request ID and appends
        both status-change and reconciliation-completed ledger events.
        """
        transaction_id = str(transaction_id)

        valid_outcomes = {
            TransactionState.SUCCEEDED,
            TransactionState.NOT_EXECUTED,
            TransactionState.UNRESOLVED,
            TransactionState.DUPLICATE_DETECTED,
        }

        if target_state not in valid_outcomes:
            raise ValueError(
                f"Invalid reconciliation outcome: {target_state}"
            )

        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    "SELECT * FROM transactions WHERE id = ?",
                    (transaction_id,),
                ).fetchone()

                if row is None:
                    raise TransactionNotFoundError(transaction_id)

                current_state = TransactionState(row["status"])

                next_state = transition(
                    current_state,
                    target_state,
                )

                request_ids_json = _append_request_id_json(
                    row,
                    otari_request_id,
                )

                updated_at = _utc_now().isoformat()

                connection.execute(
                    """
                    UPDATE transactions
                    SET status = ?,
                        updated_at = ?,
                        otari_request_ids_json = ?
                    WHERE id = ?
                    """,
                    (
                        next_state.value,
                        updated_at,
                        request_ids_json,
                        transaction_id,
                    ),
                )

                self.ledger_store.append_event_in_transaction(
                    connection,
                    LedgerEventCreate(
                        txn_id=transaction_id,
                        type="TRANSACTION_STATUS_CHANGED",
                        payload={
                            "from_status": current_state.value,
                            "to_status": next_state.value,
                            "reason": "reconciliation_completed",
                        },
                    ),
                )

                self.ledger_store.append_event_in_transaction(
                    connection,
                    LedgerEventCreate(
                        txn_id=transaction_id,
                        type="RECONCILIATION_COMPLETED",
                        payload={
                            "outcome": next_state.value,
                            "reason": reason,
                            "evidence": evidence,
                            "otari_request_id": otari_request_id,
                        },
                    ),
                )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        updated = self.get_transaction(transaction_id)

        if updated is None:
            raise TransactionNotFoundError(transaction_id)

        return updated

    def fail_reconciliation_attempt(
        self,
        transaction_id: UUID | str,
        return_state: TransactionState,
        *,
        error_code: str,
        otari_request_id: str | None = None,
    ) -> Transaction:
        """
        Restore the transaction to its previous uncertain state when
        reconciliation cannot obtain reliable evidence.
        """
        transaction_id = str(transaction_id)

        if return_state not in {
            TransactionState.INDETERMINATE,
            TransactionState.UNRESOLVED,
        }:
            raise ValueError(
                f"Invalid reconciliation recovery state: {return_state}"
            )

        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    "SELECT * FROM transactions WHERE id = ?",
                    (transaction_id,),
                ).fetchone()

                if row is None:
                    raise TransactionNotFoundError(transaction_id)

                current_state = TransactionState(row["status"])

                next_state = transition(
                    current_state,
                    return_state,
                )

                request_ids_json = _append_request_id_json(
                    row,
                    otari_request_id,
                )

                updated_at = _utc_now().isoformat()

                connection.execute(
                    """
                    UPDATE transactions
                    SET status = ?,
                        updated_at = ?,
                        otari_request_ids_json = ?
                    WHERE id = ?
                    """,
                    (
                        next_state.value,
                        updated_at,
                        request_ids_json,
                        transaction_id,
                    ),
                )

                self.ledger_store.append_event_in_transaction(
                    connection,
                    LedgerEventCreate(
                        txn_id=transaction_id,
                        type="TRANSACTION_STATUS_CHANGED",
                        payload={
                            "from_status": current_state.value,
                            "to_status": next_state.value,
                            "reason": "reconciliation_probe_failed",
                        },
                    ),
                )

                self.ledger_store.append_event_in_transaction(
                    connection,
                    LedgerEventCreate(
                        txn_id=transaction_id,
                        type="RECONCILIATION_ATTEMPT_FAILED",
                        payload={
                            "error_code": error_code,
                            "otari_request_id": otari_request_id,
                            "restored_state": next_state.value,
                        },
                    ),
                )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        updated = self.get_transaction(transaction_id)

        if updated is None:
            raise TransactionNotFoundError(transaction_id)

        return updated
