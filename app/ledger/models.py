
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class LedgerEventCreate(BaseModel):
    """Input required to append a new ledger event."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str = Field(default_factory=lambda: str(uuid4()))
    txn_id: str = Field(min_length=1)
    type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any]
    ts: datetime = Field(default_factory=utc_now)

    @field_validator("type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Event type cannot be empty")

        return value

    @field_validator("txn_id")
    @classmethod
    def validate_transaction_id(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Transaction ID cannot be empty")

        return value

    @field_validator("ts")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Ledger timestamps must be timezone-aware")

        return value.astimezone(UTC)


class LedgerEvent(LedgerEventCreate):
    """Complete persisted ledger event."""

    seq: int = Field(ge=1)
    prev_hash: str = Field(min_length=1)
    hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class LedgerVerificationResult(BaseModel):
    """Result of verifying a transaction's event chain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    valid: bool
    txn_id: str
    events_checked: int = Field(ge=0)
    first_invalid_seq: int | None = Field(default=None, ge=1)
    reason: str | None = None
