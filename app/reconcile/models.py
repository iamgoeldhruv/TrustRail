
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.txn.states import TransactionState


class IssueActivityEvidence(BaseModel):
    """Validated evidence retrieved from the GitHub MCP server."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository: str
    issue_number: int = Field(gt=0)
    issue_state: Literal["open", "closed"]
    is_closed: bool
    total_comments: int = Field(ge=0)
    txn_id: str = Field(min_length=1, max_length=128)
    marker_comment_count: int = Field(ge=0)
    matching_comment_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_consistency(self):
        if self.is_closed != (self.issue_state == "closed"):
            raise ValueError("Issue state and is_closed are inconsistent")

        if self.marker_comment_count != len(self.matching_comment_ids):
            raise ValueError(
                "Marker count does not match the matching comment IDs"
            )

        if len(set(self.matching_comment_ids)) != len(
            self.matching_comment_ids
        ):
            raise ValueError("Duplicate comment IDs in evidence")

        if any(comment_id <= 0 for comment_id in self.matching_comment_ids):
            raise ValueError("Comment IDs must be positive")

        return self


class ReconciliationResult(BaseModel):
    """Deterministic reconciliation decision for a transaction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str
    outcome: Literal[
        TransactionState.SUCCEEDED,
        TransactionState.NOT_EXECUTED,
        TransactionState.UNRESOLVED,
        TransactionState.DUPLICATE_DETECTED,
    ]
    reason: str
    evidence: IssueActivityEvidence
    reconciled_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
