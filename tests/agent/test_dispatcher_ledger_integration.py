from datetime import UTC, datetime

import pytest

from app.agent.dispatcher import AgentToolDispatcher
from app.agent.tool_handlers import AgentToolError
from app.db.connection import get_connection
from app.db.migrations import run_migrations
from app.ledger.store import LedgerStore


class ReadHandlers:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def list_issues(self, arguments):
        self.calls += 1
        if self.fail:
            raise AgentToolError("MCP read failed")
        return {"issues": []}

    async def get_issue(self, arguments):
        self.calls += 1
        if self.fail:
            raise AgentToolError("MCP read failed")
        return {"number": arguments["issue_number"]}

    def propose_close(self, *, arguments, run_id):
        return {"status": "PROPOSED"}


class FailingLedger:
    def append_event(self, event):
        raise OSError("database unavailable")


def _database(tmp_path):
    database = tmp_path / "ledger.db"
    run_migrations(db_path=database)
    now = datetime.now(UTC).isoformat()
    with get_connection(database) as connection:
        connection.execute(
            """
            INSERT INTO policies (id, version, nl_text, json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("policy-1", 1, "policy", "{}", "ACTIVE", now),
        )
        connection.executemany(
            """
            INSERT INTO runs (id, policy_id, user_request, planner_model, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("run-1", "policy-1", "read issues", "planner", now),
                ("run-2", "policy-1", "read issue", "planner", now),
            ],
        )
        connection.commit()
    return database


@pytest.mark.asyncio
async def test_real_ledger_persists_run_scoped_read_chain(tmp_path):
    database = _database(tmp_path)
    ledger = LedgerStore(database)
    handlers = ReadHandlers()
    dispatcher = AgentToolDispatcher(handlers, ledger)

    assert await dispatcher.dispatch(
        tool_name="list_issues",
        arguments_json="{}",
        run_id="run-1",
    ) == {"issues": []}
    assert await dispatcher.dispatch(
        tool_name="get_issue",
        arguments_json='{"issue_number": 4}',
        run_id="run-1",
    ) == {"number": 4}
    assert await dispatcher.dispatch(
        tool_name="list_issues",
        arguments_json="{}",
        run_id="run-2",
    ) == {"issues": []}
    assert handlers.calls == 3

    reopened = LedgerStore(database)
    events = reopened.get_events(run_id="run-1")
    assert [event.seq for event in events] == [1, 2]
    assert [event.type for event in events] == [
        "READ_TOOL_CALL",
        "READ_TOOL_CALL",
    ]
    assert reopened.verify_chain(run_id="run-1").valid is True
    run_two_events = reopened.get_events(run_id="run-2")
    assert [event.seq for event in run_two_events] == [1]
    assert reopened.verify_chain(run_id="run-2").valid is True


@pytest.mark.asyncio
async def test_proposal_does_not_create_read_audit_event(tmp_path):
    database = _database(tmp_path)
    dispatcher = AgentToolDispatcher(ReadHandlers(), LedgerStore(database))

    result = await dispatcher.dispatch(
        tool_name="propose_close",
        arguments_json='{"issue_number":4,"reason":"inactive"}',
        run_id="run-1",
    )

    assert result == {"status": "PROPOSED"}
    assert LedgerStore(database).get_events(run_id="run-1") == []


@pytest.mark.asyncio
async def test_failed_mcp_read_is_audited_and_not_retried(tmp_path):
    database = _database(tmp_path)
    ledger = LedgerStore(database)
    handlers = ReadHandlers(fail=True)
    dispatcher = AgentToolDispatcher(handlers, ledger)

    result = await dispatcher.dispatch(
        tool_name="list_issues",
        arguments_json="{}",
        run_id="run-1",
    )

    assert result["error"]["code"] == "tool_execution_error"
    assert handlers.calls == 1
    event = ledger.get_events(run_id="run-1")[0]
    assert event.payload["outcome"] == "FAILED"


@pytest.mark.asyncio
async def test_audit_failure_is_not_reported_as_read_success():
    handlers = ReadHandlers()
    dispatcher = AgentToolDispatcher(handlers, FailingLedger())

    result = await dispatcher.dispatch(
        tool_name="get_issue",
        arguments_json='{"issue_number": 4}',
        run_id="run-1",
    )

    assert result["error"]["code"] == "audit_logging_error"
    assert handlers.calls == 1
