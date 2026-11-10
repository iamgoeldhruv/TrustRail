
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.approvals.models import Approval, ApprovalDecision
from app.approvals.service import ApprovalService
from app.txn.store import TransactionStore
from pydantic import BaseModel, ConfigDict, Field, field_validator

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["Approvals"],
)


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approver: str = Field(min_length=1)

    @field_validator("approver")
    @classmethod
    def validate_approver(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Approver must not be empty")
        return value


def _record_decision(
    transaction_id: str,
    approver: str,
    decision: ApprovalDecision,
    request: Request,
) -> Approval:
    store: TransactionStore = request.app.state.transaction_store
    service: ApprovalService | None = request.app.state.approval_service

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Approval service is not configured",
        )

    transaction = store.get_transaction(transaction_id)

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    try:
        return service.decide(
            txn_id=transaction_id,
            approver=approver,
            decision=decision,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{transaction_id}/approve",
    response_model=Approval,
    status_code=status.HTTP_201_CREATED,
)
def approve_transaction(
    transaction_id: str,
    body: ApprovalDecisionRequest,
    request: Request,
) -> Approval:
    return _record_decision(
        transaction_id,
        body.approver,
        ApprovalDecision.APPROVE,
        request,
    )


@router.post(
    "/{transaction_id}/reject",
    response_model=Approval,
    status_code=status.HTTP_201_CREATED,
)
def reject_transaction(
    transaction_id: str,
    body: ApprovalDecisionRequest,
    request: Request,
) -> Approval:
    return _record_decision(
        transaction_id,
        body.approver,
        ApprovalDecision.REJECT,
        request,
    )
