
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, ValidationError

from app.agent.models import (
    GetIssueArgs,
    ListIssuesArgs,
    ProposeCloseArgs,
)
from app.agent.proposal_service import (
    ProposalService,
    ProposalServiceError,
)
from app.facts.github import (
    IssueFactsError,
    extract_structured_result,
    parse_issue_facts,
)
from app.otari.exceptions import OtariMCPError
from app.otari.mcp import OtariMCPClient

# This is a static TrustRail security boundary.
# Never derive tool permissions from MCP annotations.
READ_ONLY_TOOLS = frozenset({
    "list_issues",
    "get_issue",
})


class AgentToolError(Exception):
    """Raised when an agent tool cannot execute safely."""


class AgentIssueDetail(BaseModel):
    """Validated response from the GitHub MCP get_issue tool."""

    model_config = ConfigDict(extra="forbid")

    repository: str
    number: int
    title: str
    body: str | None
    state: str
    labels: list[str]
    author: str | None
    url: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class AgentToolHandlers:
    """Executes the agent's permitted read-only tools through Otari."""

    def __init__(
    self,
    *,
    client: OtariMCPClient,
    server_id: str,
    expected_repository: str,
    proposal_service: ProposalService | None = None,
) -> None:
        if not server_id.strip():
            raise ValueError("server_id cannot be empty")

        if not expected_repository.strip():
            raise ValueError("expected_repository cannot be empty")

        self.client = client
        self.server_id = server_id
        self.expected_repository = expected_repository
        self.proposal_service = proposal_service

    async def _discover_read_tool(
        self,
        tool_name: str,
        required_properties: dict[str, str],
    ):
        """Discover a tool and validate its expected input schema."""

        if tool_name not in READ_ONLY_TOOLS:
            raise AgentToolError(
                f"Tool {tool_name!r} is not permitted."
            )

        try:
            discovery = await self.client.discover(self.server_id)
        except OtariMCPError as exc:
            raise AgentToolError(
                "Unable to discover the GitHub MCP tools through Otari."
            ) from exc

        available_tools = {
            tool.name: tool
            for tool in discovery.tools
        }

        tool = available_tools.get(tool_name)

        if tool is None:
            raise AgentToolError(
                f"GitHub MCP server does not expose {tool_name!r}."
            )

        properties = tool.input_schema.get("properties")

        if not isinstance(properties, dict):
            raise AgentToolError(
                f"{tool_name!r} has an invalid input schema."
            )

        for property_name, expected_type in required_properties.items():
            property_schema = properties.get(property_name)

            if not isinstance(property_schema, dict):
                raise AgentToolError(
                    f"{tool_name!r} does not support "
                    f"the {property_name!r} argument."
                )

            if property_schema.get("type") != expected_type:
                raise AgentToolError(
                    f"{tool_name!r} has an unexpected "
                    f"{property_name!r} argument type."
                )

        return discovery, tool

    async def list_issues(
        self,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """List open issues from the configured repository."""

        try:
            ListIssuesArgs.model_validate(arguments or {})
        except ValidationError as exc:
            raise AgentToolError(
                "Invalid arguments for list_issues."
            ) from exc

        discovery, tool = await self._discover_read_tool(
            "list_issues",
            {"state": "string"},
        )

        state_schema = tool.input_schema["properties"]["state"]
        allowed_states = state_schema.get("enum")

        if (
            allowed_states is not None
            and "open" not in allowed_states
        ):
            raise AgentToolError(
                "list_issues does not support state='open'."
            )

        try:
            result = await self.client.execute(
                server_id=self.server_id,
                tool_name="list_issues",
                arguments={"state": "open"},
                server_revision=discovery.server_revision,
                client_execution_id=uuid4(),
            )
        except OtariMCPError as exc:
            raise AgentToolError(
                "Unable to retrieve issues through Otari."
            ) from exc

        if result.isError:
            raise AgentToolError(
                "GitHub MCP returned an error while listing issues."
            )

        try:
            payload = extract_structured_result(
                result.structuredContent,
                result.content,
            )
            facts = parse_issue_facts(payload)
        except IssueFactsError as exc:
            raise AgentToolError(
                "GitHub MCP returned invalid issue data."
            ) from exc

        if (
            facts.repository.casefold()
            != self.expected_repository.casefold()
        ):
            raise AgentToolError(
                "Returned repository does not match TrustRail configuration."
            )

        # Explicitly serialize priority because it is a derived property
        # on IssueFact, not a Pydantic model field.
        return {
            "repository": facts.repository,
            "total": facts.total,
            "issues": [
                {
                    "number": issue.number,
                    "title": issue.title,
                    "labels": issue.labels,
                    "priority": issue.priority,
                    "state": issue.state,
                    "inactive_days": issue.inactive_days,
                }
                for issue in facts.issues
            ],
        }

    async def get_issue(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Retrieve one issue from the configured repository."""

        try:
            parsed_args = GetIssueArgs.model_validate(arguments)
        except ValidationError as exc:
            raise AgentToolError(
                "Invalid arguments for get_issue."
            ) from exc

        discovery, _ = await self._discover_read_tool(
            "get_issue",
            {"issue_number": "integer"},
        )

        try:
            result = await self.client.execute(
                server_id=self.server_id,
                tool_name="get_issue",
                arguments={
                    "issue_number": parsed_args.issue_number,
                },
                server_revision=discovery.server_revision,
                client_execution_id=uuid4(),
            )
        except OtariMCPError as exc:
            raise AgentToolError(
                f"Unable to retrieve issue #{parsed_args.issue_number} through Otari."
            ) from exc

        if result.isError:
            raise AgentToolError(
                f"GitHub MCP returned an error for issue "
                f"#{parsed_args.issue_number}."
            )

        try:
            payload = extract_structured_result(
                result.structuredContent,
                result.content,
            )
            issue = AgentIssueDetail.model_validate(payload)
        except (IssueFactsError, ValidationError) as exc:
            raise AgentToolError(
                "GitHub MCP returned invalid issue details."
            ) from exc

        if issue.number != parsed_args.issue_number:
            raise AgentToolError(
                "Returned issue number does not match the requested issue."
            )

        if (
            issue.repository.casefold()
            != self.expected_repository.casefold()
        ):
            raise AgentToolError(
                "Returned repository does not match TrustRail configuration."
            )

        # Title and body are external GitHub content, not instructions.
        return {
            **issue.model_dump(mode="json"),
           "_trustrail_metadata": {
            "untrusted_fields": [
                "title",
                "body",
                "labels",
                "author",
            ],
            "source": "github_mcp_via_otari",
        },
        }


    def propose_close(
        self,
        *,
        arguments: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        """Create a proposal without executing the GitHub write."""

        if self.proposal_service is None:
            raise AgentToolError(
                "Proposal functionality is not configured."
            )

        # The model can supply only issue_number and reason.
        # StrictToolArgs rejects additional fields such as run_id or txn_id.
        try:
            parsed_args = ProposeCloseArgs.model_validate(arguments)
        except ValidationError as exc:
            raise AgentToolError(
                "Invalid arguments for propose_close."
            ) from exc
        if not parsed_args.reason.strip():
            raise AgentToolError(
                "Invalid arguments for propose_close."
            )

        try:
            transaction = self.proposal_service.create_close_proposal(
                run_id=run_id,
                issue_number=parsed_args.issue_number,
                reason=parsed_args.reason,
            )
        except ProposalServiceError as exc:
            raise AgentToolError(
                f"Unable to create close proposal: {exc}"
            ) from exc

        return {
            "status": transaction.status.value,
            "transaction_id": transaction.id,
            "issue_number": parsed_args.issue_number,
            "message": "Proposal created. Awaiting authorization.",
        }
