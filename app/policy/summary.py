from app.policy.models import Policy


def generate_policy_summary(policy: Policy) -> str:
    close_issue = policy.actions.close_issue

    lines = [
        f"Repository: {policy.repo}",
    ]

    if not close_issue.allowed:
        lines.append("Closing issues is disabled.")
    else:
        lines.append("Closing issues is enabled.")

        conditions = close_issue.conditions

        if conditions is not None:
            lines.append(
                f"Issues must be inactive for at least "
                f"{conditions.inactive_days_gte} days."
            )

            if conditions.priority_not_in:
                priorities = ", ".join(conditions.priority_not_in)
                lines.append(
                    f"Issues with these priorities are excluded: "
                    f"{priorities}."
                )
            else:
                lines.append("No priorities are excluded.")

            if conditions.require_priority_label:
                lines.append(
                    "Issues must have a priority label."
                )
            else:
                lines.append(
                    "A priority label is not required."
                )

    if close_issue.requires_approval:
        lines.append("Human approval is required before closing.")
    else:
        lines.append("Human approval is not required before closing.")

    lines.append(
        f"Maximum actions per run: "
        f"{policy.limits.max_actions_per_run}."
    )

    lines.append(
        f"Audit logging: "
        f"{'enabled' if policy.audit.enabled else 'disabled'}."
    )

    return "\n".join(lines)