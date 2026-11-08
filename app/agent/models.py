from pydantic import BaseModel, ConfigDict, Field


class StrictToolArgs(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )


class ListIssuesArgs(StrictToolArgs):
    """Arguments for listing issues in the configured repository."""


class GetIssueArgs(StrictToolArgs):
    """Arguments for retrieving one issue."""

    issue_number: int = Field(
        ge=1,
        description="The positive GitHub issue number.",
    )


class ProposeCloseArgs(StrictToolArgs):
    """Arguments for proposing that an issue be closed."""

    issue_number: int = Field(
        ge=1,
        description="The positive GitHub issue number.",
    )

    reason: str = Field(
        min_length=1,
        max_length=1000,
        description="The reason for proposing that this issue be closed.",
    )