
import asyncio
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
import json
from pathlib import Path
from mcp_github.middleware import DropResponseMiddleware
import hmac

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp_github.admin_models import (
    FaultUpdateRequest,
    FaultUpdateResponse,
)
from mcp_github.fault_injection import fault_controller
logger = logging.getLogger("trustrail.mcp.github")
from mcp_github.fault_injection import (
    FaultMode,
    fault_controller,
)
from mcp_github.fault_injection import (
    FaultMode,
    fault_controller,
    mark_response_for_drop,
)
mcp = MCPServer("TrustRail-GitHub")

def _load_demo_ages(path: Path) -> dict[int, int]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid demo ages configuration: {path}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Demo ages configuration must be a JSON object.")

    overrides: dict[int, int] = {}

    for issue_number, inactive_days in data.items():
        try:
            number = int(issue_number)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid issue number in demo ages: {issue_number}"
            ) from exc

        if number <= 0:
            raise ValueError("Issue numbers must be positive.")

        if type(inactive_days) is not int or inactive_days < 0:
            raise ValueError(
                f"Invalid inactive_days value for issue #{number}."
            )

        overrides[number] = inactive_days

    return overrides

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
    marker_count: int
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
    demo_ages = _load_demo_ages(settings.demo_ages_file)

    for issue in github_issues:
        updated_at = issue.updated_at

        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        actual_inactive_days = max(
            0,
            (now - updated_at).days,
        )

        inactive_days = demo_ages.get(
            issue.number,
            actual_inactive_days,
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

    marker_count = sum(
        comment.body.count(marker)
        for comment in comments
    )

    return IssueActivityResponse(
        repository=settings.mcp_github_repo,
        issue_number=issue.number,
        issue_state=issue.state,
        is_closed=issue.state == "closed",
        total_comments=len(comments),
        txn_id=txn_id,
        marker_comment_count=len(matching_comment_ids),
        marker_count=marker_count,
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
        fault_mode = await fault_controller.consume_mode()
        logger.info(
            "Consumed fault mode %s for issue #%s",
            fault_mode.value,
            issue_number,
        )
        if fault_mode == FaultMode.FAIL_BEFORE_APPLY:
            raise RuntimeError("Injected failure before GitHub write.")
        comment = await client.create_issue_comment(
            issue_number=issue_number,
            body=comment_body,
        )

        if fault_mode == FaultMode.PARTIAL:
            raise RuntimeError("Injected failure after comment creation.")
        # 4. Close the issue.
        # If this request fails or its response is lost, the comment
        # remains as evidence for TrustRail reconciliation.
        # Do not retry this PATCH.
        closed_issue = await client.close_issue(issue_number)
        if fault_mode == FaultMode.DROP_AFTER_APPLY:
            mark_response_for_drop()
        if fault_mode == FaultMode.DELAY_AFTER_APPLY:
            await asyncio.sleep(50)

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
async def update_fault_mode(request: Request) -> JSONResponse:
    settings = GitHubSettings()

    authorization = request.headers.get("Authorization", "")

    if not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing admin token."},
        )

    provided_token = authorization.removeprefix("Bearer ").strip()
    expected_token = settings.trustrail_admin_token.get_secret_value()

    if not hmac.compare_digest(provided_token, expected_token):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing admin token."},
        )

    try:
        payload = await request.json()
        fault_request = FaultUpdateRequest.model_validate(payload)

    except (ValueError, ValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid fault configuration."},
        )

    await fault_controller.set_mode(fault_request.mode)

    response = FaultUpdateResponse(
        mode=fault_request.mode,
        updated=True,
    )

    logger.info("Admin updated fault mode to %s", fault_request.mode.value)

    return JSONResponse(
        status_code=200,
        content=response.model_dump(mode="json"),
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
        security_settings = None

    mcp_app = mcp.streamable_http_app(
    json_response=True,
    transport_security=security_settings,
    )

    mcp_app = DropResponseMiddleware(mcp_app)

    return Starlette(
        routes=[
            Route(
                "/admin/fault",
                endpoint=update_fault_mode,
                methods=["POST"],
            ),
            Mount("/", app=mcp_app),
        ]
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
