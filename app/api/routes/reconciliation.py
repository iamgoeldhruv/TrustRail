
from fastapi import APIRouter, HTTPException, Request, status

from app.reconcile.engine import (
    ReconciliationEngine,
    ReconciliationError,
)
from app.reconcile.models import ReconciliationResult
from app.txn.states import TransactionState
from app.txn.store import TransactionStore


router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["Reconciliation"],
)


@router.post(
    "/{transaction_id}/reconcile",
    response_model=ReconciliationResult,
)
async def reconcile_transaction(
    transaction_id: str,
    request: Request,
) -> ReconciliationResult:
    engine: ReconciliationEngine | None = (
        request.app.state.reconciliation_engine
    )

    store: TransactionStore = request.app.state.transaction_store

    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reconciliation service is not configured",
        )

    # Check whether the transaction exists.
    transaction = store.get_transaction(transaction_id)

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    # Only uncertain transactions can be reconciled.
    eligible_states = {
        TransactionState.INDETERMINATE,
        TransactionState.UNRESOLVED,
    }

    if transaction.status not in eligible_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transaction in state {transaction.status} "
                "is not eligible for reconciliation"
            ),
        )

    try:
        return await engine.reconcile(transaction_id)

    except ReconciliationError as exc:
        message = str(exc)

        if "not eligible for reconciliation" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=message,
        ) from exc
