import pytest

from app.authz.engine import evaluate
from app.authz.models import (
    Action,
    DecisionKind,
    Fact,
    RunState,
)
from app.policy.models import Policy


def make_policy(
    *,
    allowed: bool = True,
    requires_approval: bool = True,
    inactive_days_gte: int = 30,
    priority_not_in: list[str] | None = None,
    require_priority_label: bool = True,
    max_actions_per_run: int = 3,
) -> Policy:
    return Policy.model_validate({
        "version": 1,
        "repo": "iamgoeldhruv/my-RPC",
        "actions": {
            "close_issue": {
                "allowed": allowed,
                "conditions": {
                    "inactive_days_gte": inactive_days_gte,
                    "priority_not_in": (
                        priority_not_in
                        if priority_not_in is not None
                        else ["P0", "P1"]
                    ),
                    "require_priority_label": require_priority_label,
                },
                "requires_approval": requires_approval,
            }
        },
        "limits": {
            "max_actions_per_run": max_actions_per_run,
        },
        "audit": {
            "enabled": True,
        },
    })


def make_action(issue_number: int = 42) -> Action:
    return Action(
        action="close_issue",
        issue_number=issue_number,
        reason="Issue has been inactive.",
    )


def make_fact(
    *,
    issue_number: int = 42,
    state: str = "open",
    priority: str | None = "P2",
    inactive_days: int = 45,
    labels: list[str] | None = None,
) -> Fact:
    return Fact(
        issue_number=issue_number,
        state=state,
        priority=priority,
        inactive_days=inactive_days,
        labels=labels if labels is not None else ["bug", "P2"],
    )


def make_run_state(count: int = 0) -> RunState:
    return RunState(budget_consumed_actions=count)

import pytest

from app.authz.engine import evaluate
from app.authz.models import (
    Action,
    DecisionKind,
    Fact,
    RunState,
)
from app.policy.models import Policy


def make_policy(
    *,
    allowed: bool = True,
    requires_approval: bool = True,
    inactive_days_gte: int = 30,
    priority_not_in: list[str] | None = None,
    require_priority_label: bool = True,
    max_actions_per_run: int = 3,
) -> Policy:
    return Policy.model_validate({
        "version": 1,
        "repo": "iamgoeldhruv/my-RPC",
        "actions": {
            "close_issue": {
                "allowed": allowed,
                "conditions": {
                    "inactive_days_gte": inactive_days_gte,
                    "priority_not_in": (
                        priority_not_in
                        if priority_not_in is not None
                        else ["P0", "P1"]
                    ),
                    "require_priority_label": require_priority_label,
                },
                "requires_approval": requires_approval,
            }
        },
        "limits": {
            "max_actions_per_run": max_actions_per_run,
        },
        "audit": {
            "enabled": True,
        },
    })


def make_action(issue_number: int = 42) -> Action:
    return Action(
        action="close_issue",
        issue_number=issue_number,
        reason="Issue has been inactive.",
    )


def make_fact(
    *,
    issue_number: int = 42,
    state: str = "open",
    priority: str | None = "P2",
    inactive_days: int = 45,
    labels: list[str] | None = None,
) -> Fact:
    return Fact(
        issue_number=issue_number,
        state=state,
        priority=priority,
        inactive_days=inactive_days,
        labels=labels if labels is not None else ["bug", "P2"],
    )


def make_run_state(count: int = 0) -> RunState:
    return RunState(budget_consumed_actions=count)

@pytest.mark.parametrize(
    ("fact_overrides", "expected_reason"),
    [
        (
            {"state": "closed"},
            "issue_not_open",
        ),
        (
            {"inactive_days": 29},
            "inactive_days_below_threshold",
        ),
        (
            {"priority": "P0"},
            "priority_blocked",
        ),
        (
            {"priority": "P1"},
            "priority_blocked",
        ),
        (
            {"priority": None},
            "priority_missing",
        ),
        (
            {"issue_number": 43},
            "fact_issue_mismatch",
        ),
    ],
)
def test_denies_invalid_issue_facts(fact_overrides, expected_reason):
    result = evaluate(
        policy=make_policy(),
        action=make_action(issue_number=42),
        facts=make_fact(**fact_overrides),
        run_state=make_run_state(),
    )

    assert result.decision == DecisionKind.DENY
    assert expected_reason in result.reasons

def test_exact_inactivity_threshold_passes():
    result = evaluate(
        policy=make_policy(inactive_days_gte=30),
        action=make_action(),
        facts=make_fact(inactive_days=30),
        run_state=make_run_state(),
    )

    assert result.decision == DecisionKind.REQUIRES_APPROVAL

def test_action_limit_reached_denies_action():
    result = evaluate(
        policy=make_policy(max_actions_per_run=3),
        action=make_action(),
        facts=make_fact(),
        run_state=make_run_state(count=3),
    )

    assert result.decision == DecisionKind.DENY
    assert result.reasons == ["action_limit_exceeded"]


def test_action_limit_not_yet_reached_allows_approval_flow():
    result = evaluate(
        policy=make_policy(max_actions_per_run=3),
        action=make_action(),
        facts=make_fact(),
        run_state=make_run_state(count=2),
    )

    assert result.decision == DecisionKind.REQUIRES_APPROVAL

def test_action_limit_reached_denies_action():
    result = evaluate(
        policy=make_policy(max_actions_per_run=3),
        action=make_action(),
        facts=make_fact(),
        run_state=make_run_state(count=3),
    )

    assert result.decision == DecisionKind.DENY
    assert result.reasons == ["action_limit_exceeded"]


def test_action_limit_not_yet_reached_allows_approval_flow():
    result = evaluate(
        policy=make_policy(max_actions_per_run=3),
        action=make_action(),
        facts=make_fact(),
        run_state=make_run_state(count=2),
    )

    assert result.decision == DecisionKind.REQUIRES_APPROVAL

def test_approval_not_required_returns_allow():
    result = evaluate(
        policy=make_policy(requires_approval=False),
        action=make_action(),
        facts=make_fact(),
        run_state=make_run_state(),
    )

    assert result.decision == DecisionKind.ALLOW