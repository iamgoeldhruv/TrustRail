import pytest
from pydantic import ValidationError

from app.agent.models import (
    GetIssueArgs,
    ListIssuesArgs,
    ProposeCloseArgs,
)
from app.agent.tools import AGENT_TOOLS


def test_exactly_three_agent_tools_are_exposed():
    names = [
        tool["function"]["name"]
        for tool in AGENT_TOOLS
    ]

    assert names == [
        "list_issues",
        "get_issue",
        "propose_close",
    ]


def test_all_tools_use_strict_function_schemas():
    for tool in AGENT_TOOLS:
        function = tool["function"]

        assert function["strict"] is True
        assert function["parameters"]["additionalProperties"] is False


def test_list_issues_accepts_empty_arguments():
    args = ListIssuesArgs.model_validate({})

    assert args.model_dump() == {}


def test_get_issue_requires_positive_issue_number():
    args = GetIssueArgs.model_validate({"issue_number": 10})

    assert args.issue_number == 10

    with pytest.raises(ValidationError):
        GetIssueArgs.model_validate({"issue_number": 0})


def test_get_issue_rejects_extra_arguments():
    with pytest.raises(ValidationError):
        GetIssueArgs.model_validate({
            "issue_number": 10,
            "repository": "someone/else",
        })


def test_propose_close_requires_reason():
    args = ProposeCloseArgs.model_validate({
        "issue_number": 10,
        "reason": "This issue is inactive.",
    })

    assert args.issue_number == 10

    with pytest.raises(ValidationError):
        ProposeCloseArgs.model_validate({
            "issue_number": 10,
        })


def test_propose_close_rejects_extra_execution_arguments():
    with pytest.raises(ValidationError):
        ProposeCloseArgs.model_validate({
            "issue_number": 10,
            "reason": "This issue is inactive.",
            "approved": True,
        })