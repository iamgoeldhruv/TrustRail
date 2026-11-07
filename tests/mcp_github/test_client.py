
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from mcp_github.client import GitHubClient
from mcp_github.config import GitHubSettings
from mcp_github.errors import GitHubConnectionError, GitHubNotFoundError


@pytest.fixture
def github_settings() -> GitHubSettings:
    return GitHubSettings(
        mcp_github_pat=SecretStr("test-token"),
        mcp_github_repo="iamgoeldhruv/LimeDraw",
    )


@pytest.fixture
def issue_payload() -> dict:
    now = datetime.now(UTC).isoformat()

    return {
        "id": 123,
        "number": 1,
        "title": "Test issue",
        "body": "Test body",
        "state": "open",
        "labels": [{"id": 1, "name": "P2"}],
        "user": {"login": "test-user", "id": 10},
        "html_url": "https://github.com/iamgoeldhruv/LimeDraw/issues/1",
        "created_at": now,
        "updated_at": now,
        "closed_at": None,
    }


def create_client(
    settings: GitHubSettings,
    handler,
) -> tuple[GitHubClient, httpx.AsyncClient]:
    transport = httpx.MockTransport(handler)

    http_client = httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=transport,
    )

    return GitHubClient(settings, http_client), http_client


@pytest.mark.asyncio
async def test_list_issues(
    github_settings,
    issue_payload,
):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/repos/iamgoeldhruv/LimeDraw/issues"
        assert request.url.params["per_page"] == "100"

        return httpx.Response(
            200,
            json=[issue_payload],
        )

    client, http_client = create_client(
        github_settings,
        handler,
    )

    try:
        issues = await client.list_issues()

        assert len(issues) == 1
        assert issues[0].number == 1
        assert issues[0].title == "Test issue"
        assert issues[0].labels[0].name == "P2"
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_list_issues_excludes_pull_requests(
    github_settings,
    issue_payload,
):
    pull_request = {
        **issue_payload,
        "id": 456,
        "number": 2,
        "pull_request": {
            "url": "https://api.github.com/repos/example"
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[issue_payload, pull_request],
        )

    client, http_client = create_client(
        github_settings,
        handler,
    )

    try:
        issues = await client.list_issues()

        assert len(issues) == 1
        assert issues[0].number == 1
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_issue(
    github_settings,
    issue_payload,
):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/issues/1")

        return httpx.Response(
            200,
            json=issue_payload,
        )

    client, http_client = create_client(
        github_settings,
        handler,
    )

    try:
        issue = await client.get_issue(1)

        assert issue.number == 1
        assert issue.body == "Test body"
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_issue_not_found(github_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"message": "Not Found"},
        )

    client, http_client = create_client(
        github_settings,
        handler,
    )

    try:
        with pytest.raises(GitHubNotFoundError):
            await client.get_issue(999)
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_issue_number_must_be_positive(
    github_settings,
):
    client, http_client = create_client(
        github_settings,
        lambda request: httpx.Response(200, json={}),
    )

    try:
        with pytest.raises(ValueError):
            await client.get_issue(0)
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_authentication_header(github_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"

        return httpx.Response(200, json=[])

    client, http_client = create_client(
        github_settings,
        handler,
    )

    try:
        await client.list_issues()
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_safe_get_retries_transient_connection_error(github_settings):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            raise httpx.RemoteProtocolError(
                "Server disconnected without sending a response"
            )

        return httpx.Response(200, json=[])

    client, http_client = create_client(github_settings, handler)

    try:
        assert await client.list_issues() == []
        assert attempts == 2
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_write_does_not_retry_connection_error(github_settings):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.RemoteProtocolError("connection dropped")

    client, http_client = create_client(github_settings, handler)

    try:
        with pytest.raises(GitHubConnectionError):
            await client.close_issue(1)
        assert attempts == 1
    finally:
        await http_client.aclose()
