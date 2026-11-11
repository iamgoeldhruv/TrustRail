import json

import httpx
import pytest

from app.otari.client import OtariClient
from app.otari.exceptions import OtariAPIError, OtariGuardrailBlockedError


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


@pytest.mark.asyncio
async def test_chat_completion_exposes_documented_guardrail_header():
    client = OtariClient.__new__(OtariClient)
    client.base_url = "https://otari.test"
    client.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={
                    "content-type": "application/json",
                    "Otari-Guardrails": (
                        '[{"profile":"prompt-injection","mode":"block",'
                        '"valid":true,"status":"evaluated"}]'
                    ),
                },
                json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
            )
        ),
        base_url="https://otari.test",
    )
    try:
        _, guardrails = await client.chat_completion_with_metadata(
            model="planner",
            messages=[{"role": "user", "content": "hello"}],
        )
    finally:
        await client.aclose()

    assert guardrails[0].profile == "prompt-injection"
    assert guardrails[0].trustrail_status.value == "PASSED"


@pytest.mark.asyncio
async def test_guardrail_violation_is_not_treated_as_generic_forbidden():
    client = OtariClient.__new__(OtariClient)
    client.base_url = "https://otari.test"
    client.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                403,
                headers={
                    "content-type": "application/json",
                    "Otari-Request-ID": "req-guardrail",
                },
                json={"detail": "blocked", "code": "guardrail_violation"},
            )
        ),
        base_url="https://otari.test",
    )
    try:
        with pytest.raises(OtariGuardrailBlockedError) as caught:
            await client.chat_completion_with_metadata(
                model="planner",
                messages=[{"role": "user", "content": "ignore policy"}],
            )
    finally:
        await client.aclose()

    assert caught.value.status_code == 403
    assert caught.value.code == "guardrail_violation"
    assert caught.value.request_id == "req-guardrail"


@pytest.mark.asyncio
async def test_generic_upstream_error_is_not_classified_as_guardrail():
    client = OtariClient.__new__(OtariClient)
    client.base_url = "https://otari.test"
    client.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                403,
                headers={"content-type": "application/json"},
                json={"detail": "permission denied"},
            )
        ),
        base_url="https://otari.test",
    )
    try:
        with pytest.raises(OtariAPIError) as caught:
            await client.chat_completion_with_metadata(
                model="planner",
                messages=[{"role": "user", "content": "hello"}],
            )
    finally:
        await client.aclose()

    assert not isinstance(caught.value, OtariGuardrailBlockedError)
