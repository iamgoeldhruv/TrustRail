import pytest

from app.policy.compiler_models import (
    AmbiguousResponse,
    PolicyDraft,
)
from app.policy.compiler_parser import (
    CompilerResponseError,
    parse_compiler_response,
)


def test_parse_valid_policy_draft():
    raw = """
    {
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
        }
    }
    """

    result = parse_compiler_response(raw)

    assert isinstance(result, PolicyDraft)


def test_parse_valid_ambiguous_response():
    raw = """
    {
        "error": "ambiguous",
        "questions": [
            "How many days of inactivity should qualify an issue as old?"
        ]
    }
    """

    result = parse_compiler_response(raw)

    assert isinstance(result, AmbiguousResponse)


def test_reject_invalid_json():
    with pytest.raises(CompilerResponseError):
        parse_compiler_response("{invalid json}")


def test_reject_markdown_fenced_json():
    raw = """
    ```json
    {"error": "ambiguous", "questions": ["Please clarify"]}
    ```
    """

    with pytest.raises(CompilerResponseError):
        parse_compiler_response(raw)


def test_reject_unknown_fields():
    raw = """
    {
        "actions": {
            "close_issue": {
                "allowed": true,
                "conditions": null,
                "requires_approval": true
            }
        },
        "unexpected": true
    }
    """

    with pytest.raises(CompilerResponseError):
        parse_compiler_response(raw)


def test_reject_unsupported_response():
    with pytest.raises(CompilerResponseError):
        parse_compiler_response('{"message": "Hello"}')


def test_reject_non_object_json():
    with pytest.raises(CompilerResponseError):
        parse_compiler_response('["not", "an", "object"]')