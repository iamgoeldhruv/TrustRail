
from uuid import uuid4

from pydantic import ValidationError

from app.authz.engine import evaluate
from app.authz.models import Action, Fact, RunState
from app.dryrun.models import (
    DryRunIssueResult,
    DryRunResponse,
    DryRunSummary,
)
from app.facts.github import (
    IssueFactsError,
    extract_structured_result,
    parse_issue_facts,
)
from app.otari.exceptions import OtariMCPError
from app.otari.mcp import OtariMCPClient
from app.policy.models import Policy
from app.policy.validator import PolicySemanticError, validate_policy


READ_ONLY_TOOLS = {"list_issues"}


class DryRunError(Exception):
    """Raised when a policy dry-run cannot be completed safely."""


async def dry_run_policy(
    policy: Policy,
    client: OtariMCPClient,
    server_id: str,
) -> DryRunResponse:
    """
    Evaluate a policy against current GitHub issue facts.

    This operation is read-only:
    - Does not create transactions.
    - Does not create approvals.
    - Does not execute GitHub write tools.
    - Does not append ledger events.
    """

    # 1. Validate policy before making external calls.
    try:
        validate_policy(policy)
    except (PolicySemanticError, ValidationError) as exc:
        raise DryRunError("Cannot dry-run an invalid policy.") from exc

    # 2. Discover available Otari MCP tools.
    try:
        discovery = await client.discover(server_id)
    except OtariMCPError as exc:
        raise DryRunError("Unable to discover Otari MCP tools.") from exc

    available_tools = {
        tool.name: tool
        for tool in discovery.tools
    }

    # 3. Enforce a static read-only tool allowlist.
    tool_name = "list_issues"

    if tool_name not in READ_ONLY_TOOLS:
        raise DryRunError("Requested tool is not permitted.")

    tool = available_tools.get(tool_name)

    if tool is None:
        raise DryRunError("Otari MCP server does not expose list_issues.")

    # 4. Verify that the tool supports fetching all issues.
    properties = tool.input_schema.get("properties", {})
    state_schema = properties.get("state")

    if state_schema is None:
        raise DryRunError("list_issues does not support the state parameter.")

    allowed_states = state_schema.get("enum")

    if allowed_states is not None and "all" not in allowed_states:
        raise DryRunError("list_issues does not support state='all'.")

    # 5. Fetch facts through Otari.
    try:
        result = await client.execute(
            server_id=server_id,
            tool_name=tool_name,
            arguments={"state": "all"},
            server_revision=discovery.server_revision,
            client_execution_id=uuid4(),
        )
        
    except OtariMCPError as exc:
        raise DryRunError("Unable to fetch GitHub issue facts through Otari.") from exc

    if result.isError:
        raise DryRunError("Otari returned an error while fetching issue facts.")

    # 6. Parse and validate the returned facts.
    try:
        payload = extract_structured_result(
            result.structuredContent,
            result.content,
        )
        issue_facts = parse_issue_facts(payload)
    except IssueFactsError as exc:
        raise DryRunError("Otari returned invalid issue facts.") from exc

    # 7. Ensure facts belong to the policy repository.
    if issue_facts.repository.casefold() != policy.repo.casefold():
        raise DryRunError(
            "The fetched repository does not match the policy repository."
        )

    # 8. Evaluate each issue independently.
    results: list[DryRunIssueResult] = []

    for issue in issue_facts.issues:
        try:
            facts = Fact(
                issue_number=issue.number,
                state=issue.state,
                labels=issue.labels,
                priority=issue.priority,
                inactive_days=issue.inactive_days,
            )
        except ValidationError as exc:
            raise DryRunError(
                f"Invalid facts received for issue #{issue.number}."
            ) from exc

        action = Action(
            action="close_issue",
            issue_number=issue.number,
            reason="Policy dry-run",
        )

        decision = evaluate(
            policy=policy,
            action=action,
            facts=facts,
            run_state=RunState(budget_consumed_actions=0),
        )

        results.append(
            DryRunIssueResult(
                issue_number=issue.number,
                title=issue.title,
                state=issue.state,
                inactive_days=issue.inactive_days,
                priority=issue.priority,
                decision=decision.decision,
                reasons=decision.reasons,
            )
        )

    # 9. Aggregate decisions.
    allowed = sum(
        r.decision.value == "ALLOW" for r in results
    )
    requires_approval = sum(
        r.decision.value == "REQUIRES_APPROVAL" for r in results
    )
    denied = sum(
        r.decision.value == "DENY" for r in results
    )
    policy_invalid = sum(
        r.decision.value == "POLICY_INVALID" for r in results
    )

    return DryRunResponse(
        repository=issue_facts.repository,
        policy_version=policy.version,
        summary=DryRunSummary(
            total_issues=len(results),
            allowed=allowed,
            requires_approval=requires_approval,
            denied=denied,
            policy_invalid=policy_invalid,
            max_actions_per_run=policy.limits.max_actions_per_run,
        ),
        results=results,
    )
