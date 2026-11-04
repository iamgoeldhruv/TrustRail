
import asyncio

import httpx

from app.otari.mcp import OtariMCPClient


def test_discover_returns_tools_and_server_revision() -> None:
    expected_payload = {
        "server_id": "test-server-id",
        "server_revision": "revision-123",
        "tools": [
            {
                "name": "get_status",
                "description": "Read status",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
                "annotations": {"readOnlyHint": True},
            },
            {
                "name": "update_status",
                "description": "Update status",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"}
                    },
                },
                "annotations": {"readOnlyHint": False},
            },
        ],
        "warnings": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == (
            "/api/v1/mcp/servers/test-server-id/tools"
        )
        assert request.headers["Authorization"] == "Bearer test-key"

        return httpx.Response(200, json=expected_payload)

    async def run_test() -> None:
        async with OtariMCPClient(
            base_url="https://api.otari.ai/api/v1",
            api_key="test-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            result = await client.discover("test-server-id")
            

            assert result.server_id == "test-server-id"
            assert result.server_revision == "revision-123"
            assert len(result.tools) == 2
            assert result.tools[0].name == "get_status"
            assert result.tools[1].name == "update_status"
            assert result.warnings == []

    asyncio.run(run_test())
