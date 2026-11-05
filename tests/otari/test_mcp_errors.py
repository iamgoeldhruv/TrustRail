
from uuid import uuid4

import httpx
import pytest

from app.otari.exceptions import (
    OtariMCPNotStartedError,
    OtariMCPOutcomeUnknownError,
    OtariMCPResponseError,
    OtariMCPServerChangedError,
)
from app.otari.mcp import OtariMCPClient


def make_error_response(
    status_code: int,
    code: str,
    execution_state: str,
    *,
    body_request_id: str = "body-123",
    header_request_id: str = "header-456",
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        headers={"Otari-Request-ID": header_request_id},
        json={
            "detail": "Test Otari error",
            "code": code,
            "execution_state": execution_state,
            "request_id": body_request_id,
        },
    )


@pytest.mark.asyncio
async def test_server_changed_maps_to_specific_exception():
    response = make_error_response(
        409,
        "mcp_server_changed",
        "not_started",
    )

    error = OtariMCPClient._parse_error_response(
        response,
        execution_request=True,
    )

    assert isinstance(error, OtariMCPServerChangedError)
    assert error.status_code == 409
    assert error.code == "mcp_server_changed"


@pytest.mark.asyncio
async def test_not_started_maps_to_safe_exception():
    response = make_error_response(
        503,
        "mcp_capacity_unavailable",
        "not_started",
    )

    error = OtariMCPClient._parse_error_response(
        response,
        execution_request=True,
    )

    assert isinstance(error, OtariMCPNotStartedError)
    assert error.execution_state == "not_started"


@pytest.mark.asyncio
async def test_outcome_unknown_maps_to_uncertain_exception():
    response = make_error_response(
        504,
        "mcp_outcome_unknown",
        "outcome_unknown",
    )

    error = OtariMCPClient._parse_error_response(
        response,
        execution_request=True,
    )

    assert isinstance(error, OtariMCPOutcomeUnknownError)
    assert error.execution_state == "outcome_unknown"


@pytest.mark.asyncio
async def test_both_request_ids_are_preserved():
    response = make_error_response(
        502,
        "mcp_outcome_unknown",
        "outcome_unknown",
    )

    error = OtariMCPClient._parse_error_response(
        response,
        execution_request=True,
    )

    assert error.body_request_id == "body-123"
    assert error.header_request_id == "header-456"
    assert error.request_id == "body-123"


@pytest.mark.asyncio
async def test_retry_after_is_preserved():
    response = make_error_response(
        503,
        "mcp_capacity_unavailable",
        "not_started",
    )

    response.headers["Retry-After"] = "5"

    error = OtariMCPClient._parse_error_response(
        response,
        execution_request=True,
    )

    assert error.retry_after == "5"


@pytest.mark.asyncio
async def test_malformed_execution_error_is_outcome_unknown():
    response = httpx.Response(
        status_code=502,
        headers={"Otari-Request-ID": "header-789"},
        json={"unexpected": "response"},
    )

    error = OtariMCPClient._parse_error_response(
        response,
        execution_request=True,
    )

    assert isinstance(error, OtariMCPOutcomeUnknownError)
    assert error.header_request_id == "header-789"


@pytest.mark.asyncio
async def test_malformed_discovery_error_is_response_error():
    response = httpx.Response(
        status_code=502,
        json={"unexpected": "response"},
    )

    error = OtariMCPClient._parse_error_response(
        response,
        execution_request=False,
    )

    assert isinstance(error, OtariMCPResponseError)


@pytest.mark.asyncio
async def test_execute_sends_exactly_one_request():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return make_error_response(
            502,
            "mcp_outcome_unknown",
            "outcome_unknown",
        )

    transport = httpx.MockTransport(handler)

    async with OtariMCPClient(
        base_url="https://example.com/api/v1",
        api_key="test-key",
        transport=transport,
    ) as client:

        with pytest.raises(OtariMCPOutcomeUnknownError):
            await client.execute(
                server_id="server-123",
                tool_name="close_issue_with_note",
                arguments={"issue_number": 42},
                server_revision="revision-123",
                client_execution_id=uuid4(),
            )

    assert request_count == 1
