from app.otari.client import OtariClient
from app.policy.compiler_models import AmbiguousResponse
from app.policy.compiler_parser import parse_compiler_response
from app.policy.compiler_validation import get_missing_policy_fields
from app.policy.compiler_builder import build_policy
from app.policy.models import Policy
from app.policy.prompts import SYSTEM_PROMPT


class PolicyCompiler:
    def __init__(
        self,
        otari_client: OtariClient,
        model: str,
    ):
        self.otari_client = otari_client
        self.model = model

    async def compile(
        self,
        user_request: str,
    ) -> Policy | AmbiguousResponse:

        if not user_request.strip():
            raise ValueError("Policy request cannot be empty.")

        response = await self.otari_client.chat_completion(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_request,
                },
            ],
        )

        content = response["choices"][0]["message"]["content"]

        parsed = parse_compiler_response(content)

        if isinstance(parsed, AmbiguousResponse):
            return parsed

        missing_fields = get_missing_policy_fields(parsed)

        if missing_fields:
            return self._build_ambiguity_response(missing_fields)

        return build_policy(parsed)

    @staticmethod
    def _build_ambiguity_response(
        missing_fields: list[str],
    ) -> AmbiguousResponse:

        question_map = {
            "actions.close_issue.allowed":
                "Should TrustRail allow closing issues?",
            "actions.close_issue.requires_approval":
                "Should closing an issue require human approval?",
            "actions.close_issue.conditions":
                "What conditions must an issue satisfy before closing?",
            "actions.close_issue.conditions.inactive_days_gte":
                "How many days of inactivity should qualify an issue for closing?",
            "actions.close_issue.conditions.priority_not_in":
                "Which priority levels should be excluded from closing? "
                "You can also specify an empty list if none should be excluded.",
            "actions.close_issue.conditions.require_priority_label":
                "Should an issue be required to have a priority label?",
        }

        questions = [
            question_map[field]
            for field in missing_fields
            if field in question_map
        ]

        if not questions:
            questions = [
                "Please clarify the conditions for the requested policy."
            ]

        return AmbiguousResponse(
            error="ambiguous",
            questions=questions,
        )