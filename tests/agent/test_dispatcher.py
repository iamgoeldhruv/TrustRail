import json

import pytest

from app.agent.dispatcher import AgentToolDispatcher
from app.agent.tool_handlers import AgentToolError


class FakeHandlers:
    async def list_issues(self, arguments):
        return {"issues": []}

    def get_issue(self, arguments):
        return {"number": arguments["issue_number"]}

    def propose_close(self, *, arguments, run_id):
        return {"run_id": run_id, "status": "PROPOSED"}


@pytest.fixture
def dispatcher():
    return AgentToolDispatcher(FakeHandlers())


@pytest.mark.asyncio
async def test_dispatches_allowed_tools(dispatcher):
    assert await dispatcher.dispatch(
        tool_name="list_issues", arguments_json="{}", run_id="run-1"
    ) == {"issues": []}
    assert await dispatcher.dispatch(
        tool_name="get_issue", arguments_json='{"issue_number": 4}', run_id="run-1"
    ) == {"number": 4}
    assert await dispatcher.dispatch(
        tool_name="propose_close",
        arguments_json='{"issue_number":4,"reason":"done"}',
        run_id="trusted-run",
    ) == {"run_id": "trusted-run", "status": "PROPOSED"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,arguments",
    [
        ("unknown", "{}"),
        ("close_issue_with_note", "{}"),
        ("list_issues", "[]"),
        ("list_issues", "{"),
        ("propose_close", '{"issue_number": 1, "reason": "x", "run_id": "bad"}'),
        ("get_issue", '{"issue_number": 0}'),
    ],
)
async def test_rejects_invalid_calls(dispatcher, tool_name, arguments):
    with pytest.raises(AgentToolError):
        await dispatcher.dispatch(
            tool_name=tool_name, arguments_json=arguments, run_id="run-1"
        )


@pytest.mark.asyncio
async def test_rejects_oversized_arguments_and_missing_run_id(dispatcher):
    with pytest.raises(AgentToolError):
        await dispatcher.dispatch(
            tool_name="list_issues", arguments_json=" " * 16_385, run_id="run-1"
        )
    with pytest.raises(AgentToolError):
        await dispatcher.dispatch(
            tool_name="propose_close",
            arguments_json=json.dumps({"issue_number": 1, "reason": "x"}),
            run_id="",
        )


@pytest.mark.asyncio
async def test_handler_error_is_safe_structured_result():
    class ErrorHandlers(FakeHandlers):
        async def list_issues(self, arguments):
            raise AgentToolError("safe failure")

    result = await AgentToolDispatcher(ErrorHandlers()).dispatch(
        tool_name="list_issues", arguments_json="{}", run_id="run-1"
    )
    assert result == {
        "error": {"code": "tool_execution_error", "message": "safe failure"}
    }
