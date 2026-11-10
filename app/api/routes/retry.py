
from fastapi import APIRouter, HTTPException, Request, status

from app.otari.exceptions import OtariMCPError
from app.txn.executor import (
    ApprovalRequiredError,
    TransactionExecutionError,
    TransactionExecutor,
)
from app.txn.models import Transaction
from app.txn.states import TransactionState
from app.txn.store import TransactionStore
from app.agent.evaluation import (
    ProposalEvaluationError,
    ProposalEvaluationService,
)

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["Retries"],
)


@router.post(
    "/{transaction_id}/retry",
    response_model=Transaction,
)

async def retry_transaction(
    transaction_id: str,
    request: Request,
) -> Transaction:
    store: TransactionStore = request.app.state.transaction_store
    executor: TransactionExecutor | None = (
        request.app.state.transaction_executor
    )

    if executor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transaction executor is not configured",
        )

    transaction = store.get_transaction(transaction_id)

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    # NOT_EXECUTED requires a completely fresh authorization
    # and a new human approval before execution.
    if transaction.status is TransactionState.NOT_EXECUTED:
        evaluator: ProposalEvaluationService | None = (
            request.app.state.proposal_evaluator
        )

        if evaluator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Proposal evaluator is not configured",
            )

        try:
            store.prepare_not_executed_retry(transaction_id)

            return await evaluator.evaluate(
                transaction_id,
                require_approval=True,
            )

        except (ValueError, ProposalEvaluationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        except OtariMCPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Otari request failed during retry authorization: {exc}",
            ) from exc

    # Prepare execution for an eligible retry.
    try:
        if transaction.status is TransactionState.FAILED_SAFE:
            store.prepare_failed_safe_retry(transaction_id)

        elif transaction.status is TransactionState.APPROVED:
            store.prepare_approved_not_executed_retry(transaction_id)

        elif transaction.status is not TransactionState.PRECHECK:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Transaction in state {transaction.status.value} "
                    "is not eligible for retry"
                ),
            )

        # The executor performs fresh PRECHECK and owns the write dispatch.
        return await executor.execute(transaction_id)

    except HTTPException:
        raise

    except (ValueError, ApprovalRequiredError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except OtariMCPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Otari request failed during retry: {exc}",
        ) from exc

    except TransactionExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
