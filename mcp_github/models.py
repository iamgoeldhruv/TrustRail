
from datetime import datetime

from pydantic import BaseModel, ConfigDict , Field


class GitHubModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class GitHubLabel(GitHubModel):
    id: int | None = None
    name: str


class GitHubUser(GitHubModel):
    login: str
    id: int | None = None


class GitHubIssue(GitHubModel):
    id: int
    number: int
    title: str
    body: str | None = None
    state: str

    labels: list[GitHubLabel] = Field(default_factory=list)

    user: GitHubUser | None = None

    html_url: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    # GitHub includes this field for pull requests.
    pull_request: dict | None = None


class GitHubComment(GitHubModel):
    id: int
    body: str
    user: GitHubUser | None = None
    created_at: datetime
    updated_at: datetime
    html_url: str | None = None
