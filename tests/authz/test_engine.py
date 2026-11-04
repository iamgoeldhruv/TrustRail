import pytest

from app.authz.engine import evaluate
from app.authz.models import (
    Action,
    DecisionKind,
    Fact,
    RunState,
)
from app.policy.models import Policy


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_policy(
    *,
    allowed: bool = True,
    requires_approval: bool = True,
    inactive_days_gte: int = 30,
    priority_not_in: list[str] | None = None,
    require_priority_label: bool = True,
    max_actions_per_run: int = 3,
    conditions: dict | None = None,
) -> Policy:
    if conditions is None and allowed:
        conditions = {
            "inactive_days_gte": inactive_days_gte,
            "priority_not_in": (
                priority_not_in
                if priority_not_in is not None
                else ["P0", "P1"]
            ),
            "require_priority_label": require_priority_label,
        }

    return Policy.model_validate({
        "version": 1,
        "repo": "iamgoeldhruv/my-RPC",
        "actions": {
            "close_issue": {
                "allowed": allowed,
                "conditions": conditions,
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


# ---------------------------------------------------------------------------
# Section 5.9: Seed data tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    (
        "issue_number",
        "priority",
        "inactive_days",
        "expected_decision",
        "expected_reason",
    ),
    [
        pytest.param(
            1,
            "P2",
            45,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="seed-01-p2-45-days",
        ),
        pytest.param(
            2,
            "P1",
            60,
            DecisionKind.DENY,
            "priority_blocked",
            id="seed-02-p1-priority-blocked",
        ),
        pytest.param(
            3,
            "P3",
            12,
            DecisionKind.DENY,
            "inactive_days_below_threshold",
            id="seed-03-p3-too-recent",
        ),
        pytest.param(
            4,
            "P2",
            90,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="seed-04-p2-90-days",
        ),
        pytest.param(
            5,
            "P0",
            50,
            DecisionKind.DENY,
            "priority_blocked",
            id="seed-05-p0-priority-blocked",
        ),
        pytest.param(
            6,
            "P3",
            70,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="seed-06-p3-70-days",
        ),
        pytest.param(
            7,
            "P3",
            55,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="seed-07-p3-55-days",
        ),
        pytest.param(
            8,
            "P2",
            40,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="seed-08-p2-40-days",
        ),
        pytest.param(
            9,
            "P3",
            35,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="seed-09-injection-issue",
        ),
        pytest.param(
            10,
            None,
            80,
            DecisionKind.DENY,
            "priority_missing",
            id="seed-10-no-priority",
        ),
    ],
)
def test_all_seed_issues(
    issue_number: int,
    priority: str | None,
    inactive_days: int,
    expected_decision: DecisionKind,
    expected_reason: str,
):
    """Every seeded issue must produce its expected authorization decision."""

    result = evaluate(
        policy=make_policy(),
        action=make_action(issue_number),
        facts=make_fact(
            issue_number=issue_number,
            priority=priority,
            inactive_days=inactive_days,
            labels=[] if priority is None else ["bug", priority],
        ),
        run_state=make_run_state(),
    )

    assert result.decision == expected_decision
    assert expected_reason in result.reasons


# ---------------------------------------------------------------------------
# Boundary and edge-case tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    (
        "fact_overrides",
        "policy_overrides",
        "run_count",
        "expected_decision",
        "expected_reason",
    ),
    [
        pytest.param(
            {"inactive_days": 30},
            {},
            0,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="exactly-at-inactivity-threshold",
        ),
        pytest.param(
            {"inactive_days": 29},
            {},
            0,
            DecisionKind.DENY,
            "inactive_days_below_threshold",
            id="one-day-below-inactivity-threshold",
        ),
        pytest.param(
            {"inactive_days": 31},
            {},
            0,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="one-day-above-inactivity-threshold",
        ),
        pytest.param(
            {"state": "closed"},
            {},
            0,
            DecisionKind.DENY,
            "issue_not_open",
            id="issue-already-closed",
        ),
        pytest.param(
            {"priority": "P0"},
            {},
            0,
            DecisionKind.DENY,
            "priority_blocked",
            id="p0-priority-blocked",
        ),
        pytest.param(
            {"priority": "P1"},
            {},
            0,
            DecisionKind.DENY,
            "priority_blocked",
            id="p1-priority-blocked",
        ),
        pytest.param(
            {"priority": None, "labels": []},
            {},
            0,
            DecisionKind.DENY,
            "priority_missing",
            id="empty-labels-and-missing-priority",
        ),
        pytest.param(
            {"priority": None, "labels": ["bug", "P2"]},
            {},
            0,
            DecisionKind.DENY,
            "priority_missing",
            id="labels-present-but-priority-unresolved",
        ),
        pytest.param(
            {"priority": None, "labels": ["P2", "P0"]},
            {},
            0,
            DecisionKind.DENY,
            "priority_missing",
            id="multiple-conflicting-priority-labels",
        ),
        pytest.param(
            {"priority": "P2", "labels": ["bug", "P2"]},
            {},
            0,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="single-valid-priority-label",
        ),
        pytest.param(
            {"issue_number": 43},
            {},
            0,
            DecisionKind.DENY,
            "fact_issue_mismatch",
            id="fact-issue-number-mismatch",
        ),
        pytest.param(
            {},
            {
                "allowed": False,
                "conditions": None,
            },
            0,
            DecisionKind.DENY,
            "action_not_allowed",
            id="action-disabled-by-policy",
        ),
        pytest.param(
            {},
            {},
            3,
            DecisionKind.DENY,
            "action_limit_exceeded",
            id="action-budget-exactly-reached",
        ),
        pytest.param(
            {},
            {},
            2,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="one-budget-slot-remaining",
        ),
        pytest.param(
            {},
            {"requires_approval": False},
            0,
            DecisionKind.ALLOW,
            "conditions_satisfied",
            id="approval-not-required",
        ),
        pytest.param(
            {"priority": None, "labels": []},
            {
                "require_priority_label": False,
                "priority_not_in": [],
            },
            0,
            DecisionKind.REQUIRES_APPROVAL,
            "conditions_satisfied",
            id="priority-not-required-by-policy",
        ),
    ],
)
def test_authorization_edge_cases(
    fact_overrides: dict,
    policy_overrides: dict,
    run_count: int,
    expected_decision: DecisionKind,
    expected_reason: str,
):
    result = evaluate(
        policy=make_policy(**policy_overrides),
        action=make_action(),
        facts=make_fact(**fact_overrides),
        run_state=make_run_state(run_count),
    )

    assert result.decision == expected_decision
    assert expected_reason in result.reasons


# ---------------------------------------------------------------------------
# Missing input tests
# ---------------------------------------------------------------------------


def test_missing_policy_returns_policy_invalid():
    result = evaluate(
        policy=None,
        action=make_action(),
        facts=make_fact(),
        run_state=make_run_state(),
    )

    assert result.decision == DecisionKind.POLICY_INVALID
    assert "policy_missing" in result.reasons


def test_missing_facts_fails_closed():
    result = evaluate(
        policy=make_policy(),
        action=make_action(),
        facts=None,
        run_state=make_run_state(),
    )

    assert result.decision == DecisionKind.DENY
    assert "facts_unavailable" in result.reasons
