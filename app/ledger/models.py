
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


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

    # Exactly one event scope must be provided.
    txn_id: str | None = Field(default=None, min_length=1)
    run_id: str | None = Field(default=None, min_length=1)

    type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any]
    ts: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_event_scope(self) -> LedgerEventCreate:
        """Ensure an event belongs to exactly one scope."""

        if (self.txn_id is None) == (self.run_id is None):
            raise ValueError(
                "Exactly one of txn_id or run_id must be provided"
            )

        return self

    @field_validator("txn_id", "run_id")
    @classmethod
    def validate_scope_id(cls, value: str | None) -> str | None:
        """Reject empty or whitespace-only scope identifiers."""

        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Scope ID cannot be empty")

        return value

    @field_validator("type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Event type cannot be empty")

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
    """Result of verifying a transaction or run event chain."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    valid: bool

    txn_id: str | None = None
    run_id: str | None = None

    events_checked: int = Field(ge=0)
    first_invalid_seq: int | None = Field(default=None, ge=1)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_event_scope(self) -> LedgerVerificationResult:
        if (self.txn_id is None) == (self.run_id is None):
            raise ValueError(
                "Exactly one of txn_id or run_id must be provided"
            )

        return self
