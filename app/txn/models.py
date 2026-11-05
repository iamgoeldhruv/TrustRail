from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.txn.states import TransactionState


class TransactionCreate(BaseModel):
    """Values required to persist a transaction."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    policy_id: str
    policy_version: int
    tool: str
    args: dict[str, Any]
    args_hash: str
    status: TransactionState = TransactionState.PROPOSED
    server_revision: str | None = None
    facts: Any | None = None
    approval_id: str | None = None
    otari_request_ids: list[str] | None = None
    attempt: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Transaction(TransactionCreate):
    """Typed representation of a persisted transaction."""

    created_at: datetime
    updated_at: datetime
