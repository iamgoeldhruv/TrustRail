from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.ledger.store import LedgerStore
from app.txn.models import Transaction
from app.txn.states import TransactionState
from app.txn.store import TransactionStore

router = APIRouter(prefix="/api/v1/ledger", tags=["Ledger"])


class LedgerVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    scope: str
    transaction_id: str
    run_id: str
    events_checked: int = Field(ge=0)
    verified_at: datetime
    first_invalid_seq: int | None = None
    reason: str | None = None


def _transaction_payload(transaction: Transaction) -> dict[str, Any]:
    return transaction.model_dump(mode="json")


def _find_transaction(transaction_id: str, request: Request) -> Transaction:
    transaction = request.app.state.transaction_store.get_transaction(transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


def _detail(transaction: Transaction, request: Request) -> dict[str, Any]:
    ledger: LedgerStore = request.app.state.ledger_store
    transaction_events = ledger.get_events(txn_id=transaction.id)
    run_events = ledger.get_events(run_id=transaction.run_id)
    reconciliation = [
        {
            "event_id": event.id,
            "timestamp": event.ts,
            **event.payload,
        }
        for event in transaction_events
        if event.type in {"RECONCILIATION_COMPLETED", "RECONCILIATION_ATTEMPT_FAILED"}
    ]
    return {
        **_transaction_payload(transaction),
        "events": [event.model_dump(mode="json") for event in transaction_events],
        "run_events": [event.model_dump(mode="json") for event in run_events],
        "reconciliation": reconciliation,
    }


@router.get("/transactions")
async def list_ledger_transactions(
    request: Request,
    search: str | None = Query(default=None, max_length=200),
    state: TransactionState | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    store: TransactionStore = request.app.state.transaction_store
    transactions = store.list_transactions(
        status=state,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [_transaction_payload(item) for item in transactions],
        "limit": limit,
        "offset": offset,
        "has_more": len(transactions) == limit,
    }


@router.get("/transactions/{transaction_id}")
async def get_ledger_transaction(
    transaction_id: str,
    request: Request,
) -> dict[str, Any]:
    return _detail(_find_transaction(transaction_id, request), request)


@router.post(
    "/transactions/{transaction_id}/verify",
    response_model=LedgerVerificationResponse,
)
async def verify_transaction_ledger(
    transaction_id: str,
    request: Request,
) -> LedgerVerificationResponse:
    transaction = _find_transaction(transaction_id, request)
    result = request.app.state.ledger_store.verify_chain(txn_id=transaction.id)
    return LedgerVerificationResponse(
        valid=result.valid,
        scope="transaction",
        transaction_id=transaction.id,
        run_id=transaction.run_id,
        events_checked=result.events_checked,
        verified_at=datetime.now(UTC),
        first_invalid_seq=result.first_invalid_seq,
        reason=result.reason,
    )
