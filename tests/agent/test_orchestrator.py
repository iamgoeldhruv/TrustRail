import pytest

from app.agent.orchestrator import AgentOrchestrator


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.responses)


class FakeDispatcher:
    def __init__(self):
        self.calls = []

    async def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        return {"issues": []}


def completion(message, usage=None):
    result = {"choices": [{"message": message}]}
    if usage is not None:
        result["usage"] = usage
    return result


@pytest.mark.asyncio
async def test_final_response_uses_configured_model_and_tools():
    client = FakeClient([completion({"role": "assistant", "content": "done"})])
    dispatcher = FakeDispatcher()
    result = await AgentOrchestrator(
        client=client,
        dispatcher=dispatcher,
        model="planner",
        max_completion_tokens=77,
    ).run(run_id="trusted", user_request="show issues")

    assert result.response == "done"
    assert client.calls[0]["model"] == "planner"
    assert client.calls[0]["max_tokens"] == 77
    assert len(client.calls[0]["tools"]) == 3


@pytest.mark.asyncio
async def test_tool_call_loop_preserves_call_id_and_trusted_run_id():
    client = FakeClient(
        [
            completion(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "list_issues", "arguments": "{}"},
                        }
                    ],
                },
                {"total_tokens": 4},
            ),
            completion({"role": "assistant", "content": "listed"}, {"total_tokens": 5}),
        ]
    )
    dispatcher = FakeDispatcher()
    result = await AgentOrchestrator(
        client=client, dispatcher=dispatcher, model="planner"
    ).run(run_id="trusted", user_request="show issues")

    assert result.response == "listed"
    assert dispatcher.calls[0]["run_id"] == "trusted"
    assert client.calls[1]["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": '{"issues":[]}',
    }
    assert result.provider_usage == {"total_tokens": 9}


@pytest.mark.asyncio
async def test_limits_stop_repeated_tool_calls():
    response = completion(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "list_issues", "arguments": "{}"},
                }
            ],
        }
    )
    client = FakeClient([response, response])
    result = await AgentOrchestrator(
        client=client,
        dispatcher=FakeDispatcher(),
        model="planner",
        max_iterations=5,
        max_tool_calls=1,
    ).run(run_id="trusted", user_request="loop")

    assert result.termination_reason == "tool_call_limit"
    assert result.tool_calls == 1
