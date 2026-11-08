import json

import httpx
import pytest

from app.otari.client import OtariClient


@pytest.mark.asyncio
async def test_chat_completion_accepts_tool_call_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "list_issues",
                                        "arguments": "{}",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    client = OtariClient.__new__(OtariClient)
    client.base_url = "https://otari.test"
    client.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://otari.test",
    )
    try:
        result = await client.chat_completion(
            model="planner",
            messages=[{"role": "user", "content": "list"}],
            tools=[{"type": "function"}],
            max_tokens=42,
        )
    finally:
        await client.aclose()

    assert result["choices"][0]["message"]["content"] is None
    assert seen["model"] == "planner"
    assert seen["max_tokens"] == 42
    assert seen["tools"] == [{"type": "function"}]
