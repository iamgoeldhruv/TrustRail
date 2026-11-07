import json

from app.core.config import settings
from app.policy.compiler_models import PolicyDraft
from app.policy.compiler_validation import get_missing_policy_fields
from app.policy.models import Policy
from app.policy.parser import parse_policy_json


DEFAULT_MAX_ACTIONS_PER_RUN = 10
DEFAULT_AUDIT_ENABLED = True


class IncompletePolicyDraftError(ValueError):
    pass


def build_policy(draft: PolicyDraft) -> Policy:
    missing_fields = get_missing_policy_fields(draft)

    if missing_fields:
        raise IncompletePolicyDraftError(
            f"Policy draft is incomplete: {', '.join(missing_fields)}"
        )

    close_issue = draft.actions.close_issue

    policy_data = {
        "version": 1,
        "repo": settings.mcp_github_repo,
        "actions": {
            "close_issue": {
                "allowed": close_issue.allowed,
                "conditions": (
                    {
                        "inactive_days_gte": (
                            close_issue.conditions.inactive_days_gte
                        ),
                        "priority_not_in": (
                            close_issue.conditions.priority_not_in
                        ),
                        "require_priority_label": (
                            close_issue.conditions.require_priority_label
                        ),
                    }
                    if close_issue.conditions is not None
                    else None
                ),
                "requires_approval": close_issue.requires_approval,
            }
        },
        "limits": {
            "max_actions_per_run": DEFAULT_MAX_ACTIONS_PER_RUN,
        },
        "audit": {
            "enabled": DEFAULT_AUDIT_ENABLED,
        },
    }

    return parse_policy_json(json.dumps(policy_data))