import json
from typing import Any

from pydantic import ValidationError

from app.facts.models import IssueListFacts


class IssueFactsError(ValueError):
    pass


def parse_issue_facts(payload: dict[str, Any]) -> IssueListFacts:
    try:
        facts = IssueListFacts.model_validate(payload)
    except ValidationError as exc:
        raise IssueFactsError(
            "Otari returned an invalid list_issues response."
        ) from exc

    if facts.total != len(facts.issues):
        raise IssueFactsError(
            "Issue count does not match the returned issue list."
        )

    if any(issue.number <= 0 for issue in facts.issues):
        raise IssueFactsError("Received an invalid issue number.")

    if any(issue.inactive_days < 0 for issue in facts.issues):
        raise IssueFactsError("Received a negative inactivity duration.")

    return facts


def extract_structured_result(
    structured_content: dict[str, Any] | None,
    content: list[dict[str, Any]],
) -> dict[str, Any]:
    if structured_content is not None:
        return structured_content

    # Fallback for MCP responses that contain JSON in text content.
    for item in content:
        if item.get("type") != "text":
            continue

        try:
            parsed = json.loads(item["text"])
        except (KeyError, TypeError, json.JSONDecodeError):
            continue

        if isinstance(parsed, dict):
            return parsed

    raise IssueFactsError(
        "Otari response did not contain structured issue facts."
    )