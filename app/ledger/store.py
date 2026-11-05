from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from app.ledger.canonical import canonical_json
from app.db.connection import get_connection
from app.ledger.hashing import GENESIS_HASH, compute_event_hash
from app.ledger.models import LedgerEvent, LedgerEventCreate
from app.ledger.models import LedgerEvent, LedgerEventCreate, LedgerVerificationResult


def _serialize_timestamp(value: datetime) -> str:
    """Serialize a timezone-aware timestamp consistently in UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Ledger timestamps must be timezone-aware")

    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    """Parse a persisted UTC timestamp."""

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class LedgerStore:
    """SQLite persistence for per-transaction append-only event chains."""

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


    def get_events(self, txn_id: str) -> list[LedgerEvent]:
        """Return a transaction's events in sequence order."""

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    txn_id,
                    seq,
                    type,
                    payload_json,
                    prev_hash,
                    hash,
                    ts
                FROM events
                WHERE txn_id = ?
                ORDER BY seq ASC
                """,
                (txn_id,),
            ).fetchall()

        return [
            LedgerEvent(
                id=row["id"],
                txn_id=row["txn_id"],
                seq=row["seq"],
                type=row["type"],
                payload=json.loads(row["payload_json"]),
                ts=_parse_timestamp(row["ts"]),
                prev_hash=row["prev_hash"],
                hash=row["hash"],
            )
            for row in rows
        ]

    def verify_chain(self, txn_id: str) -> LedgerVerificationResult:
        """
        Verify the integrity of a transaction's event chain.

        This method is read-only. It checks sequence continuity,
        previous-hash links, and recomputed event hashes.
        """

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    txn_id,
                    seq,
                    type,
                    payload_json,
                    prev_hash,
                    hash,
                    ts
                FROM events
                WHERE txn_id = ?
                ORDER BY seq ASC
                """,
                (txn_id,),
            ).fetchall()

        previous_hash = GENESIS_HASH
        expected_seq = 1
        events_checked = 0

        for row in rows:
            seq = row["seq"]

            if seq != expected_seq:
                return LedgerVerificationResult(
                    valid=False,
                    txn_id=txn_id,
                    events_checked=events_checked,
                    first_invalid_seq=expected_seq,
                    reason=(
                        f"Sequence gap or invalid sequence: expected {expected_seq}, found {seq}"
                    ),
                )

            if row["prev_hash"] != previous_hash:
                return LedgerVerificationResult(
                    valid=False,
                    txn_id=txn_id,
                    events_checked=events_checked,
                    first_invalid_seq=seq,
                    reason="Previous hash does not match the preceding event",
                )

            try:
                payload = json.loads(row["payload_json"])

                if not isinstance(payload, dict):
                    raise ValueError("Event payload must be a JSON object")

                event_data = {
                    "id": row["id"],
                    "txn_id": row["txn_id"],
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
                return LedgerVerificationResult(
                    valid=False,
                    txn_id=txn_id,
                    events_checked=events_checked,
                    first_invalid_seq=seq,
                    reason=f"Event data cannot be verified: {exc}",
                )

            if row["hash"] != expected_hash:
                return LedgerVerificationResult(
                    valid=False,
                    txn_id=txn_id,
                    events_checked=events_checked,
                    first_invalid_seq=seq,
                    reason="Event hash does not match the recomputed hash",
                )

            previous_hash = row["hash"]
            expected_seq += 1
            events_checked += 1

        return LedgerVerificationResult(
            valid=True,
            txn_id=txn_id,
            events_checked=events_checked,
            first_invalid_seq=None,
            reason=None,
        )
    
    def append_event_in_transaction(
        self,
        connection: sqlite3.Connection,
        event: LedgerEventCreate,
    ) -> LedgerEvent:
        """
        Append an event using an existing SQLite transaction.

        The caller owns the connection and is responsible for commit/rollback.
        """

        previous = connection.execute(
            """
            SELECT seq, hash
            FROM events
            WHERE txn_id = ?
            ORDER BY seq DESC
            LIMIT 1
            """,
            (event.txn_id,),
        ).fetchone()

        if previous is None:
            seq = 1
            prev_hash = GENESIS_HASH
        else:
            seq = previous["seq"] + 1
            prev_hash = previous["hash"]

        timestamp = _serialize_timestamp(event.ts)

        event_data = {
            "id": event.id,
            "txn_id": event.txn_id,
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
                seq,
                type,
                payload_json,
                prev_hash,
                hash,
                ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.txn_id,
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
            seq=seq,
            type=event.type,
            payload=event.payload,
            ts=event.ts,
            prev_hash=prev_hash,
            hash=event_hash,
        )

