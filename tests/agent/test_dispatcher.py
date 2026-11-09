
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


class FakeLedger:
    def __init__(self):
        self.events = []
        self.should_fail = False

    def append_event(self, event):
        if self.should_fail:
            raise RuntimeError("Database unavailable")

        self.events.append(event)
        return event


@pytest.fixture
def ledger():
    return FakeLedger()


@pytest.fixture
def dispatcher(ledger):
    return AgentToolDispatcher(FakeHandlers(), ledger)


@pytest.mark.asyncio
async def test_dispatches_allowed_tools(dispatcher, ledger):
    # list_issues
    result = await dispatcher.dispatch(
        tool_name="list_issues",
        arguments_json="{}",
        run_id="run-1",
    )
    assert result == {"issues": []}

    # get_issue
    result = await dispatcher.dispatch(
        tool_name="get_issue",
        arguments_json='{"issue_number": 4}',
        run_id="run-1",
    )
    assert result == {"number": 4}

    # propose_close
    result = await dispatcher.dispatch(
        tool_name="propose_close",
        arguments_json='{"issue_number":4,"reason":"done"}',
        run_id="trusted-run",
    )
    assert result == {
        "run_id": "trusted-run",
        "status": "PROPOSED",
    }

    # Only the two read operations should be logged.
    assert len(ledger.events) == 2
    assert all(
        event.type == "READ_TOOL_CALL"
        for event in ledger.events
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,arguments",
    [
        ("unknown", "{}"),
        ("close_issue_with_note", "{}"),
        ("list_issues", "[]"),
        ("list_issues", "{"),
        (
            "propose_close",
            '{"issue_number": 1, "reason": "x", "run_id": "bad"}',
        ),
        ("get_issue", '{"issue_number": 0}'),
    ],
)
async def test_rejects_invalid_calls(
    dispatcher,
    ledger,
    tool_name,
    arguments,
):
    with pytest.raises(AgentToolError):
        await dispatcher.dispatch(
            tool_name=tool_name,
            arguments_json=arguments,
            run_id="run-1",
        )

    assert ledger.events == []


@pytest.mark.asyncio
async def test_rejects_oversized_arguments_and_missing_run_id(
    dispatcher,
    ledger,
):
    with pytest.raises(AgentToolError):
        await dispatcher.dispatch(
            tool_name="list_issues",
            arguments_json=" " * 16_385,
            run_id="run-1",
        )

    with pytest.raises(AgentToolError):
        await dispatcher.dispatch(
            tool_name="propose_close",
            arguments_json=json.dumps(
                {"issue_number": 1, "reason": "x"}
            ),
            run_id="",
        )

    assert ledger.events == []


@pytest.mark.asyncio
async def test_handler_error_is_safe_structured_result(ledger):
    class ErrorHandlers(FakeHandlers):
        async def list_issues(self, arguments):
            raise AgentToolError("Sensitive internal details")

    dispatcher = AgentToolDispatcher(ErrorHandlers(), ledger)

    result = await dispatcher.dispatch(
        tool_name="list_issues",
        arguments_json="{}",
        run_id="run-1",
    )

    assert result == {
        "error": {
            "code": "tool_execution_error",
            "message": "The requested read operation failed.",
        }
    }

    assert len(ledger.events) == 1
    assert ledger.events[0].payload["outcome"] == "FAILED"


@pytest.mark.asyncio
async def test_successful_read_is_logged(dispatcher, ledger):
    result = await dispatcher.dispatch(
        tool_name="get_issue",
        arguments_json='{"issue_number": 42}',
        run_id="run-1",
    )

    assert result == {"number": 42}
    assert len(ledger.events) == 1

    event = ledger.events[0]

    assert event.run_id == "run-1"
    assert event.txn_id is None
    assert event.type == "READ_TOOL_CALL"
    assert event.payload == {
        "tool_name": "get_issue",
        "arguments": {"issue_number": 42},
        "outcome": "SUCCEEDED",
    }


@pytest.mark.asyncio
async def test_failed_read_is_logged(dispatcher, ledger):
    class ErrorHandlers(FakeHandlers):
        async def list_issues(self, arguments):
            raise AgentToolError("Sensitive internal details")

    dispatcher.handlers = ErrorHandlers()

    result = await dispatcher.dispatch(
        tool_name="list_issues",
        arguments_json="{}",
        run_id="run-1",
    )

    assert result["error"]["code"] == "tool_execution_error"
    assert (
        "Sensitive internal details"
        not in result["error"]["message"]
    )

    assert len(ledger.events) == 1

    event = ledger.events[0]

    assert event.payload["tool_name"] == "list_issues"
    assert event.payload["outcome"] == "FAILED"
    assert event.payload["error"]["code"] == "tool_execution_error"


@pytest.mark.asyncio
async def test_propose_close_does_not_create_read_event(
    dispatcher,
    ledger,
):
    result = await dispatcher.dispatch(
        tool_name="propose_close",
        arguments_json='{"issue_number": 4, "reason": "done"}',
        run_id="run-1",
    )

    assert result["status"] == "PROPOSED"
    assert ledger.events == []


@pytest.mark.asyncio
async def test_audit_failure_does_not_return_read_success(
    dispatcher,
    ledger,
):
    ledger.should_fail = True

    result = await dispatcher.dispatch(
        tool_name="get_issue",
        arguments_json='{"issue_number": 42}',
        run_id="run-1",
    )

    assert result["error"]["code"] == "audit_logging_error"
    assert "number" not in result


@pytest.mark.asyncio
async def test_read_requires_valid_run_id(dispatcher, ledger):
    with pytest.raises(AgentToolError):
        await dispatcher.dispatch(
            tool_name="get_issue",
            arguments_json='{"issue_number": 42}',
            run_id=" ",
        )

    assert ledger.events == []


@pytest.mark.asyncio
async def test_invalid_read_arguments_are_not_logged(
    dispatcher,
    ledger,
):
    with pytest.raises(AgentToolError):
        await dispatcher.dispatch(
            tool_name="get_issue",
            arguments_json='{"issue_number": 0}',
            run_id="run-1",
        )

    assert ledger.events == []
