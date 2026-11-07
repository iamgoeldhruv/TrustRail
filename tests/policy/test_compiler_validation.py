from app.policy.compiler_models import (
    ActionsDraft,
    CloseIssueDraft,
    IssueConditionsDraft,
    PolicyDraft,
)
from app.policy.compiler_validation import get_missing_policy_fields


def test_complete_policy_draft_returns_no_missing_fields():
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

    assert get_missing_policy_fields(draft) == []


def test_missing_approval_is_detected():
    draft = PolicyDraft(
        actions=ActionsDraft(
            close_issue=CloseIssueDraft(
                allowed=True,
                conditions=IssueConditionsDraft(
                    inactive_days_gte=30,
                    priority_not_in=[],
                    require_priority_label=True,
                ),
            )
        )
    )

    assert "actions.close_issue.requires_approval" in (
        get_missing_policy_fields(draft)
    )


def test_missing_conditions_are_detected():
    draft = PolicyDraft(
        actions=ActionsDraft(
            close_issue=CloseIssueDraft(
                allowed=True,
                requires_approval=True,
            )
        )
    )

    missing = get_missing_policy_fields(draft)

    assert "actions.close_issue.conditions" in missing


def test_missing_condition_fields_are_detected():
    draft = PolicyDraft(
        actions=ActionsDraft(
            close_issue=CloseIssueDraft(
                allowed=True,
                conditions=IssueConditionsDraft(
                    inactive_days_gte=30,
                ),
                requires_approval=True,
            )
        )
    )

    missing = get_missing_policy_fields(draft)

    assert "actions.close_issue.conditions.priority_not_in" in missing
    assert (
        "actions.close_issue.conditions.require_priority_label"
        in missing
    )


def test_disabled_action_with_no_conditions_is_valid():
    draft = PolicyDraft(
        actions=ActionsDraft(
            close_issue=CloseIssueDraft(
                allowed=False,
                conditions=None,
                requires_approval=True,
            )
        )
    )

    assert get_missing_policy_fields(draft) == []


def test_disabled_action_with_conditions_is_rejected():
    draft = PolicyDraft(
        actions=ActionsDraft(
            close_issue=CloseIssueDraft(
                allowed=False,
                conditions=IssueConditionsDraft(
                    inactive_days_gte=30,
                ),
                requires_approval=True,
            )
        )
    )

    missing = get_missing_policy_fields(draft)

    assert any("conditions must be null" in item for item in missing)