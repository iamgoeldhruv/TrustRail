
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

from app.ledger.canonical import canonical_json_bytes


GENESIS_HASH = "GENESIS"
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_RESERVED_FIELDS = {"prev_hash", "hash"}


def validate_previous_hash(prev_hash: str) -> None:
    """Validate a previous hash or the genesis marker."""

    if prev_hash == GENESIS_HASH:
        return

    if not _SHA256_PATTERN.fullmatch(prev_hash):
        raise ValueError("Previous hash must be GENESIS or a valid SHA-256 hash")


def compute_event_hash(
    prev_hash: str,
    event_data: Mapping[str, Any],
) -> str:
    """
    Compute an event's SHA-256 hash.

    event_data must contain the event fields excluding prev_hash and hash.
    """

    validate_previous_hash(prev_hash)

    if not isinstance(event_data, Mapping):
        raise TypeError("Event data must be a mapping")

    reserved = _RESERVED_FIELDS.intersection(event_data.keys())
    if reserved:
        raise ValueError(
            f"Event data must not contain reserved fields: {sorted(reserved)}"
        )

    previous_hash_bytes = prev_hash.encode("ascii")
    event_bytes = canonical_json_bytes(event_data)

    return hashlib.sha256(previous_hash_bytes + event_bytes).hexdigest()
