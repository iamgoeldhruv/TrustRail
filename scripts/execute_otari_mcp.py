import asyncio
import json
import os
import sys
from uuid import uuid4

from app.otari.mcp import OtariMCPClient, OtariMCPError


async def run() -> None:
    base_url = os.environ.get("OTARI_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("OTARI_API_KEY", "")
    server_id = os.environ.get("OTARI_MCP_SERVER_ID", "")

    missing = [
        name
        for name, value in (
            ("OTARI_BASE_URL", base_url),
            ("OTARI_API_KEY", api_key),
            ("OTARI_MCP_SERVER_ID", server_id),
        )
        if not value
    ]

    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")

    async with OtariMCPClient(
        base_url=base_url,
        api_key=api_key,
        timeout=45.0,
    ) as client:
        try:
            # Step 1: Discover the server and its current revision.
            discovery = await client.discover(server_id)
            

            print("MCP discovery successful")
            print(f"Server ID: {discovery.server_id}")
            print(f"Server revision: {discovery.server_revision}")

            # Step 2: Verify that the requested tool is available.
            tool_name = "update_status"

            available_tools = {tool.name for tool in discovery.tools}

            if tool_name not in available_tools:
                raise RuntimeError(
                    f"{tool_name} is not available in the "
                    f"discovered tool allowlist. "
                    f"Available tools: {sorted(available_tools)}"
                )

            # Step 3: Generate a unique execution correlation ID.
            execution_id = uuid4()

            print(f"\nExecuting tool: {tool_name}")
            print(f"Execution ID: {execution_id}")

            # Step 4: Execute the read-only tool through Otari.
            result = await client.execute(
                server_id=discovery.server_id,
                tool_name=tool_name,
                arguments={"message": "TrustRail fault injection experiment"},
                server_revision=discovery.server_revision,
                client_execution_id=uuid4(),
            )

            # Step 5: Display the native MCP result.
            print("\n--- MCP Execution Result ---")
            print(
                json.dumps(
                    result.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    indent=2,
                )
            )

            if result.isError:
                print("\nThe MCP tool returned an error.")
                sys.exit(1)

            print("\nMCP tool execution successful.")

        except OtariMCPError as exc:
            print("\nOtari MCP execution failed.")
            print(f"Message: {exc}")

            if exc.status_code is not None:
                print(f"HTTP status: {exc.status_code}")

            if exc.code:
                print(f"Otari error code: {exc.code}")

            if exc.execution_state:
                print(f"Execution state: {exc.execution_state}")

            if exc.request_id:
                print(f"Otari request ID: {exc.request_id}")

            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
