from typing import Literal

from pydantic import Field

from app.policy.models import StrictModel


class AmbiguousResponse(StrictModel):
    error: Literal["ambiguous"]
    questions: list[str] = Field(min_length=1)

from pydantic import Field

from app.policy.models import StrictModel


class IssueConditionsDraft(StrictModel):
    inactive_days_gte: int | None = Field(default=None, ge=1, le=3650)
    priority_not_in: list[str] | None = None
    require_priority_label: bool | None = None


class CloseIssueDraft(StrictModel):
    allowed: bool | None = None
    conditions: IssueConditionsDraft | None = None
    requires_approval: bool | None = None


class ActionsDraft(StrictModel):
    close_issue: CloseIssueDraft


class PolicyDraft(StrictModel):
    actions: ActionsDraft