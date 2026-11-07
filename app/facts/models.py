from pydantic import BaseModel, ConfigDict, Field


class IssueFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    title: str
    labels: list[str] = Field(default_factory=list)
    state: str
    inactive_days: int

    @property
    def priority(self) -> str | None:
        for label in self.labels:
            normalized = label.strip().upper()
            if normalized in {"P0", "P1", "P2", "P3"}:
                return normalized
        return None


class IssueListFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str
    total: int
    issues: list[IssueFact]