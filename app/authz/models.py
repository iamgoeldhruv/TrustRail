from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )


class DecisionKind(str, Enum):
    ALLOW = "ALLOW"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    DENY = "DENY"
    POLICY_INVALID = "POLICY_INVALID"


class Fact(StrictModel):
    issue_number: int = Field(ge=1)
    state: Literal["open", "closed"]
    labels: list[str]
    priority: str | None
    inactive_days: int = Field(ge=0)


class Action(StrictModel):
    action: Literal["close_issue"]
    issue_number: int = Field(ge=1)
    reason: str = Field(min_length=1)


class Decision(StrictModel):
    decision: DecisionKind
    reasons: list[str] = Field(default_factory=list)

class RunState(StrictModel):
    budget_consumed_actions: int = Field(ge=0)