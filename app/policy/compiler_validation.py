from app.policy.compiler_models import PolicyDraft


def get_missing_policy_fields(draft: PolicyDraft) -> list[str]:
    missing: list[str] = []

    close_issue = draft.actions.close_issue

    if close_issue.allowed is None:
        missing.append("actions.close_issue.allowed")
        return missing

    if close_issue.requires_approval is None:
        missing.append("actions.close_issue.requires_approval")

    if not close_issue.allowed:
        if close_issue.conditions is not None:
            missing.append(
                "actions.close_issue.conditions must be null "
                "when closing is disabled"
            )
        return missing

    conditions = close_issue.conditions

    if conditions is None:
        missing.append("actions.close_issue.conditions")
        return missing

    if conditions.inactive_days_gte is None:
        missing.append("actions.close_issue.conditions.inactive_days_gte")

    if conditions.priority_not_in is None:
        missing.append("actions.close_issue.conditions.priority_not_in")

    if conditions.require_priority_label is None:
        missing.append(
            "actions.close_issue.conditions.require_priority_label"
        )

    return missing