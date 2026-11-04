
from app.policy.models import Policy


class PolicySemanticError(ValueError):
    pass

def validate_policy(policy: Policy) -> None:
    close_issue = policy.actions.close_issue
    if not close_issue.allowed and close_issue.conditions is not None:
        raise PolicySemanticError(
            "POLICY_INVALID: close_issue is not allowed, "
            "but conditions have been configured."
        )
