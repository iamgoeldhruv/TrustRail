
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from mcp_github.fault_injection import FaultMode
from mcp_github.server import close_issue_with_note


@pytest.fixture
def issue():
    return SimpleNamespace(
        number=1,
        state="open",
    )


@pytest.fixture
def comment():
    return SimpleNamespace(
        id=101,
        html_url="https://github.com/test/repo/issues/1#issuecomment-101",
    )


@pytest.fixture
def settings_factory():
    def factory(*, demo_enabled: bool):
        return SimpleNamespace(
            trustrail_enable_naive_demo=demo_enabled,
            mcp_github_repo="test/repo",
        )

    return factory


@pytest.fixture
def github_client(issue, comment):
    client = AsyncMock()
    client.get_issue.return_value = issue
    client.get_issue_comments.return_value = []
    client.create_issue_comment.return_value = comment

    async def close_issue(issue_number):
        issue.state = "closed"
        return SimpleNamespace(number=issue_number, state="closed")

    client.close_issue.side_effect = close_issue
    return client


@pytest.fixture
def patched_server(github_client, settings_factory):
    class FakeGitHubClient:
        def __init__(self, *, settings):
            self.settings = settings

        async def __aenter__(self):
            return github_client

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

    async def run(
        *,
        demo_flag: bool,
        demo_enabled: bool,
    ):
        with (
            patch(
                "mcp_github.server.GitHubSettings",
                return_value=settings_factory(
                    demo_enabled=demo_enabled
                ),
            ),
            patch(
                "mcp_github.server.GitHubClient",
                FakeGitHubClient,
            ),
            patch(
                "mcp_github.server.fault_controller.consume_mode",
                new_callable=AsyncMock,
                return_value=FaultMode.NONE,
            ),
        ):
            return await close_issue_with_note(
                issue_number=1,
                note="Closing stale issue",
                txn_id="demo-txn-123",
                demo_allow_duplicate=demo_flag,
            )

    return run


@pytest.mark.asyncio
async def test_normal_execution_succeeds(
    patched_server,
    github_client,
):
    result = await patched_server(
        demo_flag=False,
        demo_enabled=False,
    )

    assert result.success is True
    assert result.issue_state == "closed"
    github_client.create_issue_comment.assert_awaited_once()
    github_client.close_issue.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_demo_request_rejected_when_server_flag_disabled(
    patched_server,
    github_client,
):
    with pytest.raises(
        ValueError,
        match="Naive demo duplicate execution is disabled",
    ):
        await patched_server(
            demo_flag=True,
            demo_enabled=False,
        )

    github_client.create_issue_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_server_demo_enabled_but_normal_request_keeps_protection(
    patched_server,
    github_client,
    issue,
):
    # First call closes the issue and creates the marker.
    await patched_server(
        demo_flag=False,
        demo_enabled=True,
    )

    # Simulate an existing transaction marker on the next call.
    github_client.get_issue_comments.return_value = [
        SimpleNamespace(
            body="Closing stale issue\n\n<!-- trustrail:txn=demo-txn-123 -->"
        )
    ]

    with pytest.raises(
        ValueError,
        match="already closed",
    ):
        await patched_server(
            demo_flag=False,
            demo_enabled=True,
        )

    assert github_client.create_issue_comment.await_count == 1


@pytest.mark.asyncio
async def test_explicit_demo_mode_allows_duplicate_comment(
    patched_server,
    github_client,
    issue,
):
    # First execution creates the comment and closes the issue.
    await patched_server(
        demo_flag=False,
        demo_enabled=True,
    )

    github_client.get_issue_comments.return_value = [
        SimpleNamespace(
            body="Closing stale issue\n\n<!-- trustrail:txn=demo-txn-123 -->"
        )
    ]

    # Second execution explicitly opts into naive demo mode.
    result = await patched_server(
        demo_flag=True,
        demo_enabled=True,
    )

    assert result.success is True
    assert github_client.create_issue_comment.await_count == 2

    # The issue was already closed, so it must not be closed again.
    assert github_client.close_issue.await_count == 1


@pytest.mark.asyncio
async def test_demo_mode_still_creates_only_one_comment_per_invocation(
    patched_server,
    github_client,
):
    await patched_server(
        demo_flag=True,
        demo_enabled=True,
    )

    github_client.create_issue_comment.assert_awaited_once()


@pytest.mark.asyncio
async def test_demo_mode_allows_closed_issue_but_normal_mode_rejects(
    patched_server,
    github_client,
    issue,
):
    issue.state = "closed"

    with pytest.raises(ValueError, match="already closed"):
        await patched_server(
            demo_flag=False,
            demo_enabled=True,
        )

    github_client.create_issue_comment.assert_not_awaited()

    result = await patched_server(
        demo_flag=True,
        demo_enabled=True,
    )

    assert result.success is True
    github_client.create_issue_comment.assert_awaited_once()
    github_client.close_issue.assert_not_awaited()
