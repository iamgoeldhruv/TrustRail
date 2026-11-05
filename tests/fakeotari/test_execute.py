import asyncio
from uuid import uuid4

import httpx
import pytest

from app.fakeotari.app import create_app
from app.fakeotari.outcomes import ExecutionOutcome
from app.fakeotari.state import FakeOtariState
from app.otari.mcp import OtariMCPClient, OtariMCPError


def _client(state: FakeOtariState) -> OtariMCPClient:
    return OtariMCPClient(
        base_url="http://fake/api/v1",
        api_key="test-key",
        transport=httpx.ASGITransport(app=create_app(state)),
    )


def test_success_and_tool_error_are_distinct() -> None:
    async def run() -> None:
        state = FakeOtariState()
        async with _client(state) as client:
            success = await client.execute(
                server_id="fake-server",
                tool_name="update_status",
                arguments={"message": "updated"},
                server_revision="revision-1",
                client_execution_id=uuid4(),
            )
            assert success.isError is False
            assert state.invocation_count == 1
            assert state.side_effect_count == 1

            state.set_next_outcome(ExecutionOutcome.IS_ERROR)
            error = await client.execute(
                server_id="fake-server",
                tool_name="update_status",
                arguments={"message": "error-result"},
                server_revision="revision-1",
                client_execution_id=uuid4(),
            )
            assert error.isError is True
            assert state.invocation_count == 2
            assert state.side_effect_count == 2

    asyncio.run(run())


def test_not_started_has_no_invocation_or_side_effect() -> None:
    async def run() -> None:
        state = FakeOtariState()
        state.set_next_outcome(ExecutionOutcome.NOT_STARTED)
        async with _client(state) as client:
            result = await client.execute(
                server_id="fake-server",
                tool_name="update_status",
                arguments={"message": "not applied"},
                server_revision="revision-1",
                client_execution_id=uuid4(),
            )
            assert result.isError is True
        assert state.execution_request_count == 1
        assert state.invocation_count == 0
        assert state.side_effect_count == 0

    asyncio.run(run())


def test_outcome_unknown_applies_side_effect_then_fails_transport() -> None:
    async def run() -> None:
        state = FakeOtariState()
        state.set_next_outcome(ExecutionOutcome.OUTCOME_UNKNOWN)
        async with _client(state) as client:
            with pytest.raises(OtariMCPError) as error:
                await client.execute(
                    server_id="fake-server",
                    tool_name="update_status",
                    arguments={"message": "applied"},
                    server_revision="revision-1",
                    client_execution_id=uuid4(),
                )
            assert error.value.execution_state == "outcome_unknown"
        assert state.execution_request_count == 1
        assert state.invocation_count == 1
        assert state.side_effect_count == 1
        assert state.status_message == "applied"

    asyncio.run(run())


def test_conflict_returns_stale_revision_error() -> None:
    async def run() -> None:
        state = FakeOtariState()
        async with _client(state) as client:
            with pytest.raises(OtariMCPError) as error:
                await client.execute(
                    server_id="fake-server",
                    tool_name="update_status",
                    arguments={"message": "not applied"},
                    server_revision="stale",
                    client_execution_id=uuid4(),
                )
            assert error.value.status_code == 409
            assert error.value.code == "mcp_server_changed"
            assert error.value.execution_state == "not_started"
        assert state.invocation_count == 0
        assert state.side_effect_count == 0

    asyncio.run(run())


def test_reset_clears_execution_state() -> None:
    state = FakeOtariState()
    state.execution_request_count = 1
    state.invocation_count = 1
    state.side_effect_count = 1
    state.status_message = "changed"
    state.reset()

    assert state.execution_request_count == 0
    assert state.invocation_count == 0
    assert state.side_effect_count == 0
    assert state.status_message == "running"
