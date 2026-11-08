
from pydantic import BaseModel, ConfigDict, Field

from app.authz.models import DecisionKind


class DryRunModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DryRunIssueResult(DryRunModel):
    issue_number: int = Field(ge=1)
    title: str
    state: str
    inactive_days: int = Field(ge=0)
    priority: str | None
    decision: DecisionKind
    reasons: list[str]


class DryRunSummary(DryRunModel):
    total_issues: int = Field(ge=0)
    allowed: int = Field(ge=0)
    requires_approval: int = Field(ge=0)
    denied: int = Field(ge=0)
    policy_invalid: int = Field(ge=0)
    max_actions_per_run: int = Field(ge=1)


class DryRunResponse(DryRunModel):
    repository: str
    policy_version: int
    summary: DryRunSummary
    results: list[DryRunIssueResult]
