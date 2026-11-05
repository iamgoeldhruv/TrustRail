
from pydantic import ValidationError

from app.policy.models import Policy
from app.policy.validator import validate_policy


def parse_policy_json(raw_json: str) -> Policy:


    policy = Policy.model_validate_json(raw_json, strict=True)

    validate_policy(policy)

    return policy
