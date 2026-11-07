import pytest

from app.policy.compiler_builder import (
    DEFAULT_AUDIT_ENABLED,
    DEFAULT_MAX_ACTIONS_PER_RUN,
    IncompletePolicyDraftError,
    build_policy,
)
from app.policy.compiler_models import (
    ActionsDraft,
    CloseIssueDraft,
    IssueConditionsDraft,
    PolicyDraft,
)


def test_build_policy_from_complete_draft(monkeypatch):
    monkeypatch.setattr(
        "app.policy.compiler_builder.settings.mcp_github_repo",
        "iamgoeldhruv/LimeDraw",
    )

    draft = PolicyDraft(
        actions=ActionsDraft(
            close_issue=CloseIssueDraft(
                allowed=True,
                conditions=IssueConditionsDraft(
                    inactive_days_gte=30,
                    priority_not_in=["P0", "P1"],
                    require_priority_label=True,
                ),
                requires_approval=True,
            )
        )
    )

    policy = build_policy(draft)

    assert policy.version == 1
    assert policy.repo == "iamgoeldhruv/LimeDraw"
    assert policy.actions.close_issue.allowed is True
    assert policy.actions.close_issue.conditions is not None
    assert policy.actions.close_issue.conditions.inactive_days_gte == 30
    assert policy.actions.close_issue.requires_approval is True
    assert policy.limits.max_actions_per_run == DEFAULT_MAX_ACTIONS_PER_RUN
    assert policy.audit.enabled is DEFAULT_AUDIT_ENABLED


def test_build_policy_rejects_incomplete_draft():
    draft = PolicyDraft(
        actions=ActionsDraft(
            close_issue=CloseIssueDraft(
                allowed=True,
                requires_approval=True,
            )
        )
    )

    with pytest.raises(IncompletePolicyDraftError):
        build_policy(draft)


def test_build_policy_with_close_issue_disabled(monkeypatch):
    monkeypatch.setattr(
        "app.policy.compiler_builder.settings.mcp_github_repo",
        "iamgoeldhruv/LimeDraw",
    )

    draft = PolicyDraft(
        actions=ActionsDraft(
            close_issue=CloseIssueDraft(
                allowed=False,
                conditions=None,
                requires_approval=True,
            )
        )
    )

    policy = build_policy(draft)

    assert policy.actions.close_issue.allowed is False
    assert policy.actions.close_issue.conditions is None