
from pydantic import ValidationError

from app.authz.models import (
    Action,
    Decision,
    DecisionKind,
    Fact,
    RunState,
)
from app.policy.models import Policy
from app.policy.validator import (
    PolicySemanticError,
    validate_policy,
)


def evaluate(
    policy: Policy | None,
    action: Action,
    facts: Fact | None,
    run_state: RunState,
) -> Decision:
    if policy is None:
        return Decision(
            decision=DecisionKind.POLICY_INVALID,
            reasons=["policy_missing"],
        )

    try:
        validate_policy(policy)
    except (PolicySemanticError, ValidationError):
        return Decision(
            decision=DecisionKind.POLICY_INVALID,
            reasons=["policy_invalid"],
        )
    if action.action != "close_issue":
        return Decision(
            decision=DecisionKind.DENY,
            reasons=["unsupported_action"],
        )
    close_issue_policy = policy.actions.close_issue

    if not close_issue_policy.allowed:
        return Decision(
            decision=DecisionKind.DENY,
            reasons=["action_not_allowed"],
        )

    if facts is None:
        return Decision(
            decision=DecisionKind.DENY,
            reasons=["facts_unavailable"],
        )

    if action.issue_number != facts.issue_number:
        return Decision(
            decision=DecisionKind.DENY,
            reasons=["fact_issue_mismatch"],
        )

    if facts.state != "open":
        return Decision(
            decision=DecisionKind.DENY,
            reasons=["issue_not_open"],
        )

    conditions = close_issue_policy.conditions

    if conditions is not None:
        if facts.inactive_days < conditions.inactive_days_gte:
            return Decision(
                decision=DecisionKind.DENY,
                reasons=["inactive_days_below_threshold"],
            )

        if facts.priority is None:
            if (
                conditions.require_priority_label
                or conditions.priority_not_in
            ):
                return Decision(
                    decision=DecisionKind.DENY,
                    reasons=["priority_missing"],
                )

        elif facts.priority in conditions.priority_not_in:
            return Decision(
                decision=DecisionKind.DENY,
                reasons=["priority_blocked"],
            )

    if (
        run_state.budget_consumed_actions
        >= policy.limits.max_actions_per_run
    ):
        return Decision(
            decision=DecisionKind.DENY,
            reasons=["action_limit_exceeded"],
        )

    if close_issue_policy.requires_approval:
        return Decision(
            decision=DecisionKind.REQUIRES_APPROVAL,
            reasons=["conditions_satisfied"],
        )

    return Decision(
        decision=DecisionKind.ALLOW,
        reasons=["conditions_satisfied"],
    )
