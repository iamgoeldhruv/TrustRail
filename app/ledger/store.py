
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.db.connection import get_connection
from app.ledger.canonical import canonical_json
from app.ledger.hashing import GENESIS_HASH, compute_event_hash
from app.ledger.models import (
    LedgerEvent,
    LedgerEventCreate,
    LedgerVerificationResult,
)


def _serialize_timestamp(value: datetime) -> str:
    """Serialize a timezone-aware timestamp consistently in UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Ledger timestamps must be timezone-aware")

    return (
        value.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _parse_timestamp(value: str) -> datetime:
    """Parse a persisted UTC timestamp."""

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _get_event_scope(
    txn_id: str | None,
    run_id: str | None,
) -> tuple[str, str]:
    """Return the scope column and identifier."""

    if (txn_id is None) == (run_id is None):
        raise ValueError(
            "Exactly one of txn_id or run_id must be provided"
        )

    if txn_id is not None:
        return "txn_id", txn_id

    return "run_id", run_id


class LedgerStore:
    """SQLite persistence for transaction and run event chains."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def append_event(self, event: LedgerEventCreate) -> LedgerEvent:
        """Append an event in its own atomic SQLite transaction."""

        with get_connection(self.db_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                result = self.append_event_in_transaction(
                    connection,
                    event,
                )

                connection.commit()
                return result

            except Exception:
                connection.rollback()
                raise

    def get_events(
        self,
        txn_id: str | None = None,
        *,
        run_id: str | None = None,
    ) -> list[LedgerEvent]:
        """Return events for a transaction or run in sequence order."""

        scope_column, scope_id = _get_event_scope(txn_id, run_id)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id,
                    txn_id,
                    run_id,
                    seq,
                    type,
                    payload_json,
                    prev_hash,
                    hash,
                    ts
                FROM events
                WHERE {scope_column} = ?
                ORDER BY seq ASC
                """,
                (scope_id,),
            ).fetchall()

        return [
            LedgerEvent(
                id=row["id"],
                txn_id=row["txn_id"],
                run_id=row["run_id"],
                seq=row["seq"],
                type=row["type"],
                payload=json.loads(row["payload_json"]),
                ts=_parse_timestamp(row["ts"]),
                prev_hash=row["prev_hash"],
                hash=row["hash"],
            )
            for row in rows
        ]

    def verify_chain(
        self,
        txn_id: str | None = None,
        *,
        run_id: str | None = None,
    ) -> LedgerVerificationResult:
        """
        Verify the integrity of a transaction or run event chain.

        Checks sequence continuity, previous-hash links, and
        recomputed event hashes. This method is read-only.
        """

        scope_column, scope_id = _get_event_scope(txn_id, run_id)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id,
                    txn_id,
                    run_id,
                    seq,
                    type,
                    payload_json,
                    prev_hash,
                    hash,
                    ts
                FROM events
                WHERE {scope_column} = ?
                ORDER BY seq ASC
                """,
                (scope_id,),
            ).fetchall()

        previous_hash = GENESIS_HASH
        expected_seq = 1
        events_checked = 0

        for row in rows:
            seq = row["seq"]

            if seq != expected_seq:
                return self._verification_failure(
                    scope_column,
                    scope_id,
                    events_checked,
                    expected_seq,
                    (
                        f"Sequence gap or invalid sequence: "
                        f"expected {expected_seq}, found {seq}"
                    ),
                )

            if row["prev_hash"] != previous_hash:
                return self._verification_failure(
                    scope_column,
                    scope_id,
                    events_checked,
                    seq,
                    "Previous hash does not match the preceding event",
                )

            try:
                payload = json.loads(row["payload_json"])

                if not isinstance(payload, dict):
                    raise ValueError("Event payload must be a JSON object")

                # Preserve the historical transaction hash structure.
                event_data = {
                    "id": row["id"],
                    scope_column: scope_id,
                    "seq": seq,
                    "type": row["type"],
                    "payload": payload,
                    "ts": row["ts"],
                }

                expected_hash = compute_event_hash(
                    previous_hash,
                    event_data,
                )

            except (ValueError, TypeError, UnicodeError) as exc:
                return self._verification_failure(
                    scope_column,
                    scope_id,
                    events_checked,
                    seq,
                    f"Event data cannot be verified: {exc}",
                )

            if row["hash"] != expected_hash:
                return self._verification_failure(
                    scope_column,
                    scope_id,
                    events_checked,
                    seq,
                    "Event hash does not match the recomputed hash",
                )

            previous_hash = row["hash"]
            expected_seq += 1
            events_checked += 1

        return self._verification_result(
            scope_column,
            scope_id,
            valid=True,
            events_checked=events_checked,
        )

    def append_event_in_transaction(
        self,
        connection: sqlite3.Connection,
        event: LedgerEventCreate,
    ) -> LedgerEvent:
        """
        Append an event using an existing SQLite transaction.

        The caller owns the connection and is responsible for
        committing or rolling back.
        """

        scope_column, scope_id = _get_event_scope(
            event.txn_id,
            event.run_id,
        )

        previous = connection.execute(
            f"""
            SELECT seq, hash
            FROM events
            WHERE {scope_column} = ?
            ORDER BY seq DESC
            LIMIT 1
            """,
            (scope_id,),
        ).fetchone()

        if previous is None:
            seq = 1
            prev_hash = GENESIS_HASH
        else:
            seq = previous["seq"] + 1
            prev_hash = previous["hash"]

        timestamp = _serialize_timestamp(event.ts)

        # Keep transaction event hashing backward-compatible.
        event_data = {
            "id": event.id,
            scope_column: scope_id,
            "seq": seq,
            "type": event.type,
            "payload": event.payload,
            "ts": timestamp,
        }

        event_hash = compute_event_hash(prev_hash, event_data)

        connection.execute(
            """
            INSERT INTO events (
                id,
                txn_id,
                run_id,
                seq,
                type,
                payload_json,
                prev_hash,
                hash,
                ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.txn_id,
                event.run_id,
                seq,
                event.type,
                canonical_json(event.payload),
                prev_hash,
                event_hash,
                timestamp,
            ),
        )

        return LedgerEvent(
            id=event.id,
            txn_id=event.txn_id,
            run_id=event.run_id,
            seq=seq,
            type=event.type,
            payload=event.payload,
            ts=event.ts,
            prev_hash=prev_hash,
            hash=event_hash,
        )

    @staticmethod
    def _verification_result(
        scope_column: str,
        scope_id: str,
        *,
        valid: bool,
        events_checked: int,
        first_invalid_seq: int | None = None,
        reason: str | None = None,
    ) -> LedgerVerificationResult:
        return LedgerVerificationResult(
            valid=valid,
            txn_id=scope_id if scope_column == "txn_id" else None,
            run_id=scope_id if scope_column == "run_id" else None,
            events_checked=events_checked,
            first_invalid_seq=first_invalid_seq,
            reason=reason,
        )

    @classmethod
    def _verification_failure(
        cls,
        scope_column: str,
        scope_id: str,
        events_checked: int,
        invalid_seq: int,
        reason: str,
    ) -> LedgerVerificationResult:
        return cls._verification_result(
            scope_column,
            scope_id,
            valid=False,
            events_checked=events_checked,
            first_invalid_seq=invalid_seq,
            reason=reason,
        )
