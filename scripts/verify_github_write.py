
import asyncio
import json
import sys
from uuid import uuid4

from app.core.config import settings
from app.otari.mcp import OtariMCPClient, OtariMCPError


ISSUE_NUMBER = 4
TXN_ID = "a6a29b66-513d-4ec6-9b60-4d07d3a98e47"
EXPECTED_REPOSITORY = "iamgoeldhruv/LimeDraw"


async def run() -> None:
    if not settings.otari_mcp_server_id:
        sys.exit("Missing OTARI_MCP_SERVER_ID in .env")

    async with OtariMCPClient(
        base_url=settings.otari_base_url,
        api_key=settings.otari_api_key,
        timeout=45.0,
    ) as client:
        try:
            # 1. Discover the current server revision.
            discovery = await client.discover(
                settings.otari_mcp_server_id
            )

            print("MCP discovery successful")
            print(f"Server ID: {discovery.server_id}")
            print(f"Server revision: {discovery.server_revision}")

            # 2. Confirm the read-only tool exists.
            available_tools = {
                tool.name for tool in discovery.tools
            }

            tool_name = "get_issue_activity"

            if tool_name not in available_tools:
                raise RuntimeError(
                    f"{tool_name} unavailable. "
                    f"Available tools: {sorted(available_tools)}"
                )

            # 3. Execute read-only verification.
            print("\nCalling read-only get_issue_activity...")
            print(f"Repository: {EXPECTED_REPOSITORY}")
            print(f"Issue: #{ISSUE_NUMBER}")
            print(f"Transaction: {TXN_ID}")

            result = await client.execute(
                server_id=discovery.server_id,
                tool_name=tool_name,
                arguments={
                    "issue_number": ISSUE_NUMBER,
                    "txn_id": TXN_ID,
                },
                server_revision=discovery.server_revision,
                client_execution_id=uuid4(),
            )

            print("\nVerification request ID:", result.otari_request_id)

            if result.isError:
                raise RuntimeError(
                    "get_issue_activity returned an MCP error"
                )

            evidence = result.structuredContent

            if evidence is None:
                print("\nNo structuredContent returned.")
                print(json.dumps(
                    result.model_dump(mode="json"),
                    indent=2,
                ))
                raise RuntimeError(
                    "Cannot independently verify without structured evidence"
                )

            print("\n--- GitHub Activity Evidence ---")
            print(json.dumps(evidence, indent=2))

            # 4. Validate the actual GitHub evidence.
            checks = {
                "repository_matches": (
                    evidence.get("repository") == EXPECTED_REPOSITORY
                ),
                "issue_number_matches": (
                    evidence.get("issue_number") == ISSUE_NUMBER
                ),
                "transaction_id_matches": (
                    evidence.get("txn_id") == TXN_ID
                ),
                "issue_is_closed": (
                    evidence.get("is_closed") is True
                    and evidence.get("issue_state") == "closed"
                ),
                "exactly_one_marker": (
                    evidence.get("marker_comment_count") == 1
                    and evidence.get("marker_count") == 1
                ),
            }

            print("\n--- Verification Checks ---")
            for name, passed in checks.items():
                print(f"{'PASS' if passed else 'FAIL'}: {name}")

            if not all(checks.values()):
                raise RuntimeError(
                    "Independent GitHub verification did not pass"
                )

            print("\nSUCCESS: GitHub write independently verified.")

        except OtariMCPError as exc:
            print("\nOtari MCP call failed.")
            print(f"Message: {exc}")

            if exc.status_code is not None:
                print(f"HTTP status: {exc.status_code}")

            if exc.code:
                print(f"Error code: {exc.code}")

            if exc.execution_state:
                print(f"Execution state: {exc.execution_state}")

            if exc.request_id:
                print(f"Request ID: {exc.request_id}")

            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
