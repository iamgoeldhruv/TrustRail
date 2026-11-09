import asyncio
from uuid import uuid4

from app.core.config import settings
from app.facts.github import (
    IssueFactsError,
    extract_structured_result,
    parse_issue_facts,
)
from app.otari.exceptions import OtariMCPError
from app.otari.mcp import OtariMCPClient


READ_ONLY_TOOLS = {"list_issues"}


def print_issue_facts(facts) -> None:
    print()
    print(f"Repository : {facts.repository}")
    print(f"Total      : {facts.total}")
    print()

    if not facts.issues:
        print("No issues found.")
        return

    for issue in facts.issues:
        priority = issue.priority or "UNSPECIFIED"
        labels = ", ".join(issue.labels) if issue.labels else "None"

        print(f"#{issue.number} - {issue.title}")
        print(f"  State       : {issue.state}")
        print(f"  Priority    : {priority}")
        print(f"  Inactive    : {issue.inactive_days} days")
        print(f"  Labels      : {labels}")
        print()


async def issues_command(
    state: str = "open",
    labels: list[str] | None = None,
) -> int:
    server_id = settings.otari_mcp_server_id

    if not server_id:
        print("Error: OTARI_MCP_SERVER_ID is not configured.")
        return 1

    try:
        async with OtariMCPClient(
            base_url=settings.otari_base_url,
            api_key=settings.otari_api_key,
            timeout=settings.otari_timeout,
        ) as client:

            # 1. Discover tools from the registered Otari MCP server.
            discovery = await client.discover(server_id)

            available_tools = {
                tool.name: tool for tool in discovery.tools
            }

            # 2. Enforce our own read-only allowlist.
            if "list_issues" not in READ_ONLY_TOOLS:
                print("Error: list_issues is not classified as read-only.")
                return 1

            tool = available_tools.get("list_issues")

            if tool is None:
                print("Error: Otari MCP server does not expose list_issues.")
                return 1

            # 3. Validate arguments against the discovered tool schema.
            properties = tool.input_schema.get("properties", {})

            if "state" not in properties:
                print("Error: list_issues schema does not support state.")
                return 1

            if labels and "labels" not in properties:
                print("Error: list_issues schema does not support labels.")
                return 1

            arguments = {"state": state}

            if labels:
                arguments["labels"] = labels

            # 4. Execute through Otari using the discovered revision.
            # This is a read-only operation. No direct GitHub API call.
            result = await client.execute(
                server_id=server_id,
                tool_name="list_issues",
                arguments=arguments,
                server_revision=discovery.server_revision,
                client_execution_id=uuid4(),
            )

            if result.isError:
                print("Error: Otari reported an MCP tool execution failure.")
                for item in result.content:
                    if item.get("type") == "text":
                        print(item.get("text", ""))
                return 1

            # 5. Parse and validate the returned facts.
            payload = extract_structured_result(
                result.structuredContent,
                result.content,
            )
            facts = parse_issue_facts(payload)

            print_issue_facts(facts)
            return 0

    except (OtariMCPError, IssueFactsError) as exc:
        print(f"Error retrieving issue facts: {exc}")
        return 1

    except Exception as exc:
        print(f"Unexpected error: {exc}")
        return 1