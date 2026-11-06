import asyncio
import json
from uuid import uuid4

from app.core.config import settings
from app.otari.exceptions import OtariMCPError
from app.otari.mcp import OtariMCPClient


async def main() -> None:
    server_id = settings.otari_mcp_server_id

    if not server_id:
        raise RuntimeError("OTARI_MCP_SERVER_ID is not configured")

    async with OtariMCPClient(
        base_url=settings.otari_base_url,
        api_key=settings.otari_api_key,
        timeout=settings.otari_timeout,
    ) as client:
        try:
            discovery = await client.discover(server_id)

            print("Discovery successful")
            print(f"Server ID: {discovery.server_id}")
            print(f"Revision: {discovery.server_revision}")

        except OtariMCPError as exc:
            print("\n--- Otari MCP Error ---")
            print(f"Message: {exc}")
            print(f"HTTP status: {exc.status_code}")
            print(f"Error code: {exc.code}")
            print(f"Execution state: {exc.execution_state}")
            print(f"Request ID: {exc.request_id}")
            print(f"Body request ID: {exc.body_request_id}")
            print(f"Header request ID: {exc.header_request_id}")
            raise

        available_tools = {
            tool.name for tool in discovery.tools
        }

        if "get_issue_activity" not in available_tools:
            raise RuntimeError(
                f"get_issue_activity not available. "
                f"Available tools: {sorted(available_tools)}"
            )

        result = await client.execute(
            server_id=discovery.server_id,
            tool_name="get_issue_activity",
            arguments={
                "issue_number": 1,
                "txn_id": str(uuid4()),
            },
            server_revision=discovery.server_revision,
            client_execution_id=uuid4(),
        )

        print(json.dumps(
            result.model_dump(mode="json", exclude_none=True),
            indent=2,
        ))


if __name__ == "__main__":
    asyncio.run(main())