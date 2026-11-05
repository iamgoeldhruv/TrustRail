import asyncio

import httpx

from app.fakeotari.app import create_app
from app.fakeotari.state import FakeOtariState


def test_chat_returns_configured_response() -> None:
    state = FakeOtariState()
    state.set_chat_response(
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "configured"},
                }
            ]
        }
    )

    async def run() -> None:
        transport = httpx.ASGITransport(app=create_app(state))
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://fake/api/v1",
        ) as client:
            response = await client.post(
                "/chat/completions",
                json={"model": "planner", "messages": [{"role": "user", "content": "hi"}]},
            )

        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == "configured"

    asyncio.run(run())


def test_chat_rejects_invalid_request() -> None:
    async def run() -> None:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://fake/api/v1",
        ) as client:
            response = await client.post("/chat/completions", json={"model": "planner"})

        assert response.status_code == 422

    asyncio.run(run())
