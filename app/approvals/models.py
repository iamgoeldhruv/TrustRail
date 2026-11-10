from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class ApprovalDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ApprovalCreate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    txn_id: str
    approver: str = Field(min_length=1)
    decision: ApprovalDecision
    binding_hash: str = Field(min_length=64, max_length=64)
    policy_hash: str | None = Field(default=None, min_length=64, max_length=64)
    decided_at: datetime


class Approval(ApprovalCreate):
    pass
