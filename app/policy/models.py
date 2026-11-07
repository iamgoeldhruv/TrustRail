
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
   

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )


class IssueConditions(StrictModel):
    

    inactive_days_gte: int = Field(ge=1, le=3650)

    priority_not_in: list[str]

    require_priority_label: bool


class CloseIssuePolicy(StrictModel):
    

    allowed: bool

    conditions: IssueConditions | None = None

    requires_approval: bool


class ActionsPolicy(StrictModel):
   
    close_issue: CloseIssuePolicy


class LimitsPolicy(StrictModel):
   

    max_actions_per_run: int = Field(ge=1, le=50)


class AuditPolicy(StrictModel):
   

    enabled: bool


class Policy(StrictModel):
    
    version: Literal[1]

    repo: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")

    actions: ActionsPolicy

    limits: LimitsPolicy

    audit: AuditPolicy


class CompiledPolicyResponse(StrictModel):
    policy: Policy
    summary: str