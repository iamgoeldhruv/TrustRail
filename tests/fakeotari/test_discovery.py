import asyncio

import httpx

from app.fakeotari.app import create_app
from app.fakeotari.state import FakeOtariState
from app.otari.mcp import OtariMCPClient


def test_discovery_returns_tools_and_revision() -> None:
    state = FakeOtariState(server_id="server", server_revision="revision-1")

    async def run() -> None:
        transport = httpx.ASGITransport(app=create_app(state))
        async with OtariMCPClient(
            base_url="http://fake/api/v1",
            api_key="test-key",
            transport=transport,
        ) as client:
            result = await client.discover("server")
            assert result.server_revision == "revision-1"
            assert [tool.name for tool in result.tools] == [
                "get_status",
                "update_status",
            ]
            assert result.tools[1].input_schema["required"] == ["message"]

            state.set_server_revision("revision-2")
            changed = await client.discover("server")
            assert changed.server_revision == "revision-2"

    asyncio.run(run())
