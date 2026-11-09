
from types import SimpleNamespace

import pytest

from app.dryrun.service import DryRunError, dry_run_policy
from app.otari.mcp import OtariMCPClient
from app.policy.models import Policy


@pytest.fixture
def policy() -> Policy:
    return Policy(
        version=1,
        repo="iamgoeldhruv/LimeDraw",
        actions={
            "close_issue": {
                "allowed": True,
                "conditions": {
                    "inactive_days_gte": 30,
                    "priority_not_in": ["P0", "P1"],
                    "require_priority_label": True,
                },
                "requires_approval": True,
            }
        },
        limits={"max_actions_per_run": 3},
        audit={"enabled": True},
    )


@pytest.fixture
def issue_payload():
    return {
        "repository": "iamgoeldhruv/LimeDraw",
        "total": 3,
        "issues": [
            {
                "number": 1,
                "title": "Old P2 issue",
                "labels": ["P2"],
                "state": "open",
                "inactive_days": 45,
            },
            {
                "number": 2,
                "title": "High priority issue",
                "labels": ["P1"],
                "state": "open",
                "inactive_days": 60,
            },
            {
                "number": 3,
                "title": "Recently active issue",
                "labels": ["P3"],
                "state": "open",
                "inactive_days": 12,
            },
        ],
    }


class FakeOtariClient:
    def __init__(self, payload, is_error=False):
        self.payload = payload
        self.is_error = is_error
        self.discover_calls = []
        self.execute_calls = []

    async def discover(self, server_id):
        self.discover_calls.append(server_id)

        return SimpleNamespace(
            server_revision="revision-1",
            tools=[
                SimpleNamespace(
                    name="list_issues",
                    input_schema={
                        "properties": {
                            "state": {"enum": ["open", "closed", "all"]}
                        }
                    },
                )
            ],
        )

    async def execute(self, **kwargs):
        self.execute_calls.append(kwargs)

        return SimpleNamespace(
            isError=self.is_error,
            structuredContent=self.payload,
            content=[],
        )


@pytest.mark.asyncio
async def test_dry_run_evaluates_issues(policy, issue_payload):
    client = FakeOtariClient(issue_payload)

    response = await dry_run_policy(
        policy=policy,
        client=client,
        server_id="github-server",
    )

    assert response.repository == policy.repo
    assert response.policy_version == 1

    assert response.summary.total_issues == 3
    assert response.summary.requires_approval == 1
    assert response.summary.denied == 2
    assert response.summary.max_actions_per_run == 3

    assert response.results[0].issue_number == 1
    assert response.results[0].decision.value == "REQUIRES_APPROVAL"

    assert response.results[1].decision.value == "DENY"
    assert response.results[2].decision.value == "DENY"


@pytest.mark.asyncio
async def test_dry_run_uses_only_list_issues(policy, issue_payload):
    client = FakeOtariClient(issue_payload)

    await dry_run_policy(
        policy=policy,
        client=client,
        server_id="github-server",
    )

    assert len(client.execute_calls) == 1

    call = client.execute_calls[0]

    assert call["tool_name"] == "list_issues"
    assert call["arguments"] == {"state": "all"}
    assert call["server_revision"] == "revision-1"


@pytest.mark.asyncio
async def test_dry_run_rejects_repository_mismatch(policy, issue_payload):
    issue_payload["repository"] = "someone/another-repo"

    client = FakeOtariClient(issue_payload)

    with pytest.raises(DryRunError, match="does not match"):
        await dry_run_policy(
            policy=policy,
            client=client,
            server_id="github-server",
        )


@pytest.mark.asyncio
async def test_dry_run_rejects_otari_error(policy, issue_payload):
    client = FakeOtariClient(issue_payload, is_error=True)

    with pytest.raises(DryRunError, match="Otari returned an error"):
        await dry_run_policy(
            policy=policy,
            client=client,
            server_id="github-server",
        )


@pytest.mark.asyncio
async def test_dry_run_rejects_malformed_facts(policy):
    malformed_payload = {
        "repository": "iamgoeldhruv/LimeDraw",
        "total": 1,
        "issues": [
            {
                "number": 1,
                "title": "Invalid issue",
                "labels": ["P2"],
                "state": "unknown",
                "inactive_days": 30,
            }
        ],
    }

    client = FakeOtariClient(malformed_payload)

    with pytest.raises(DryRunError, match="Invalid facts"):
        await dry_run_policy(
            policy=policy,
            client=client,
            server_id="github-server",
        )
