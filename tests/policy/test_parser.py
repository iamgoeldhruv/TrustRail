
import pytest
from pydantic import ValidationError

from app.policy import (
    PolicySemanticError,
    parse_policy_json,
)


VALID_POLICY = """
{
    "version": 1,
    "repo": "owner/trustrail-sandbox",
    "actions": {
        "close_issue": {
            "allowed": true,
            "conditions": {
                "inactive_days_gte": 30,
                "priority_not_in": ["P0", "P1"],
                "require_priority_label": true
            },
            "requires_approval": true
        }
    },
    "limits": {
        "max_actions_per_run": 3
    },
    "audit": {
        "enabled": true
    }
}
"""


def test_valid_policy_is_parsed():
    policy = parse_policy_json(VALID_POLICY)

    assert policy.version == 1
    assert policy.repo == "owner/trustrail-sandbox"
    assert policy.actions.close_issue.allowed is True
    assert policy.actions.close_issue.conditions.inactive_days_gte == 30
    assert policy.limits.max_actions_per_run == 3


def test_unknown_root_field_is_rejected():
    raw = VALID_POLICY.replace(
        '"version": 1,',
        '"version": 1, "unexpected": true,',
    )

    with pytest.raises(ValidationError):
        parse_policy_json(raw)


def test_unknown_nested_field_is_rejected():
    raw = VALID_POLICY.replace(
        '"allowed": true,',
        '"allowed": true, "unexpected": true,',
    )

    with pytest.raises(ValidationError):
        parse_policy_json(raw)


@pytest.mark.parametrize("days", [0, 3651])
def test_inactive_days_out_of_bounds_are_rejected(days):
    raw = VALID_POLICY.replace(
        '"inactive_days_gte": 30',
        f'"inactive_days_gte": {days}',
    )

    with pytest.raises(ValidationError):
        parse_policy_json(raw)


@pytest.mark.parametrize("limit", [0, 51])
def test_max_actions_out_of_bounds_are_rejected(limit):
    raw = VALID_POLICY.replace(
        '"max_actions_per_run": 3',
        f'"max_actions_per_run": {limit}',
    )

    with pytest.raises(ValidationError):
        parse_policy_json(raw)


def test_unsupported_policy_version_is_rejected():
    raw = VALID_POLICY.replace(
        '"version": 1',
        '"version": 2',
    )

    with pytest.raises(ValidationError):
        parse_policy_json(raw)


def test_allowed_false_with_conditions_is_rejected():
    raw = VALID_POLICY.replace(
        '"allowed": true',
        '"allowed": false',
    )

    with pytest.raises(PolicySemanticError):
        parse_policy_json(raw)


def test_malformed_json_is_rejected():
    with pytest.raises(ValidationError):
        parse_policy_json('{"version": 1,')
