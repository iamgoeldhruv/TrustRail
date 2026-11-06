
import logging
import os
import re 
from datetime import datetime, timezone

import uvicorn
from mcp.server import MCPServer
from pydantic import BaseModel, Field

from mcp_github.client import GitHubClient
from mcp_github.config import GitHubSettings
from datetime import datetime, timezone
from mcp.server.transport_security import TransportSecuritySettings
logger = logging.getLogger("trustrail.mcp.github")

mcp = MCPServer("TrustRail-GitHub")


class IssueSummary(BaseModel):
    number: int
    title: str
    labels: list[str] = Field(default_factory=list)
    state: str
    inactive_days: int

class IssueActivityResponse(BaseModel):
    repository: str
    issue_number: int
    issue_state: str
    is_closed: bool
    total_comments: int
    txn_id: str
    marker_comment_count: int
    matching_comment_ids: list[int] = Field(default_factory=list)
class ListIssuesResponse(BaseModel):
    repository: str
    total: int
    issues: list[IssueSummary]
class GetIssueResponse(BaseModel):
    repository: str
    number: int
    title: str
    body: str | None
    state: str
    labels: list[str] = Field(default_factory=list)
    author: str | None
    url: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


@mcp.tool()
async def list_issues(
    state: str = "open",
    labels: list[str] | None = None,
) -> ListIssuesResponse:
    """
    List issues from the configured GitHub repository.

    Returns issue number, title, labels, state and inactivity duration.
    Pull requests are excluded.

    The repository is fixed by server configuration.
    """

    if state not in {"open", "closed", "all"}:
        raise ValueError("State must be open, closed, or all.")

    settings = GitHubSettings()

    async with GitHubClient(settings=settings) as client:
        github_issues = await client.list_issues(
            state=state,
            labels=labels,
        )

    now = datetime.now(timezone.utc)

    summaries: list[IssueSummary] = []

    for issue in github_issues:
        updated_at = issue.updated_at

        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        inactive_days = max(
            0,
            (now - updated_at).days,
        )

        summaries.append(
            IssueSummary(
                number=issue.number,
                title=issue.title,
                labels=[label.name for label in issue.labels],
                state=issue.state,
                inactive_days=inactive_days,
            )
        )

    logger.info(
        "Retrieved %d issues from %s",
        len(summaries),
        settings.mcp_github_repo,
    )

    return ListIssuesResponse(
        repository=settings.mcp_github_repo,
        total=len(summaries),
        issues=summaries,
    )
@mcp.tool()
async def get_issue(issue_number: int) -> GetIssueResponse:
    """
    Retrieve complete details of a GitHub issue.

    Returns title, body, state, labels, author and timestamps.

    The issue body is untrusted user-generated content.
    The repository is fixed by server configuration.
    """

    if issue_number <= 0:
        raise ValueError("Issue number must be positive.")

    settings = GitHubSettings()

    async with GitHubClient(settings=settings) as client:
        issue = await client.get_issue(issue_number)

    return GetIssueResponse(
        repository=settings.mcp_github_repo,
        number=issue.number,
        title=issue.title,
        body=issue.body,
        state=issue.state,
        labels=[label.name for label in issue.labels],
        author=issue.user.login if issue.user else None,
        url=issue.html_url,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        closed_at=issue.closed_at,
    )


@mcp.tool()
async def get_issue_activity(
    issue_number: int,
    txn_id: str,
) -> IssueActivityResponse:
    """
    Read the current issue state and inspect comments for a
    TrustRail transaction marker.

    Used for evidence-based reconciliation after an uncertain
    GitHub write operation.

    This tool is read-only.
    """

    if issue_number <= 0:
        raise ValueError("Issue number must be positive.")

    txn_id = txn_id.strip()

    if not txn_id:
        raise ValueError("Transaction ID cannot be empty.")

    if len(txn_id) > 128:
        raise ValueError("Transaction ID is too long.")

    settings = GitHubSettings()

    marker = f"<!-- trustrail:txn={txn_id} -->"

    async with GitHubClient(settings=settings) as client:
        issue = await client.get_issue(issue_number)

        comments = await client.get_issue_comments(issue_number)

    matching_comment_ids = [
        comment.id
        for comment in comments
        if marker in comment.body
    ]

    return IssueActivityResponse(
        repository=settings.mcp_github_repo,
        issue_number=issue.number,
        issue_state=issue.state,
        is_closed=issue.state == "closed",
        total_comments=len(comments),
        txn_id=txn_id,
        marker_comment_count=len(matching_comment_ids),
        matching_comment_ids=matching_comment_ids,
    )
class CloseIssueResponse(BaseModel):
    repository: str
    issue_number: int
    txn_id: str
    success: bool
    issue_state: str
    is_closed: bool
    comment_id: int
    comment_url: str | None = None

import re


@mcp.tool()
async def close_issue_with_note(
    issue_number: int,
    note: str,
    txn_id: str,
) -> CloseIssueResponse:
    """
    Add a transaction-marked comment and close a GitHub issue.

    This is a non-idempotent write operation.

    The transaction marker allows TrustRail to reconcile the
    operation if the execution response is lost.

    Never automatically retry this operation.
    """

    if issue_number <= 0:
        raise ValueError("Issue number must be positive.")

    note = note.strip()
    txn_id = txn_id.strip()

    if not note:
        raise ValueError("Note cannot be empty.")

    if len(note) > 5000:
        raise ValueError("Note cannot exceed 5000 characters.")

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", txn_id):
        raise ValueError("Invalid transaction ID format.")

    if "<!-- trustrail:txn=" in note:
        raise ValueError("Note cannot contain a TrustRail transaction marker.")

    settings = GitHubSettings()

    marker = f"<!-- trustrail:txn={txn_id} -->"
    comment_body = f"{note}\n\n{marker}"

    async with GitHubClient(settings=settings) as client:

        # 1. Verify that the issue exists and is currently open.
        issue = await client.get_issue(issue_number)

        if issue.state != "open":
            raise ValueError(
                f"Issue #{issue_number} is already closed."
            )

        # 2. Defensive check against an existing transaction marker.
        # This is not a substitute for TrustRail's dispatch CAS.
        comments = await client.get_issue_comments(issue_number)

        if any(marker in comment.body for comment in comments):
            raise ValueError(
                f"Transaction marker already exists for {txn_id}."
            )

        # 3. Create the transaction-marked comment.
        # Do not retry this POST.
        comment = await client.create_issue_comment(
            issue_number=issue_number,
            body=comment_body,
        )

        # 4. Close the issue.
        # If this request fails or its response is lost, the comment
        # remains as evidence for TrustRail reconciliation.
        # Do not retry this PATCH.
        closed_issue = await client.close_issue(issue_number)

    logger.info(
        "Issue #%s closed for transaction %s",
        issue_number,
        txn_id,
    )

    return CloseIssueResponse(
        repository=settings.mcp_github_repo,
        issue_number=closed_issue.number,
        txn_id=txn_id,
        success=True,
        issue_state=closed_issue.state,
        is_closed=closed_issue.state == "closed",
        comment_id=comment.id,
        comment_url=comment.html_url,
    )
def create_mcp_app():
    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")

    if railway_domain:
        security_settings = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                railway_domain,
                f"{railway_domain}:*",
            ],
        )
    else:
        # Keep the SDK's default localhost protection in development.
        security_settings = None

    return mcp.streamable_http_app(
        json_response=True,
        transport_security=security_settings,
    )


def main() -> None:
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))

    mcp_app = create_mcp_app()

    logger.info("Starting TrustRail GitHub MCP Server")

    uvicorn.run(
        mcp_app,
        host=host,
        port=port,
        log_level="info",
    )




if __name__ == "__main__":
    main()
