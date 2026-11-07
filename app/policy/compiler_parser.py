import json

from pydantic import ValidationError

from app.policy.compiler_models import (
    AmbiguousResponse,
    PolicyDraft,
)


class CompilerResponseError(ValueError):
    """Raised when the LLM returns an invalid compiler response."""


def parse_compiler_response(
    raw_response: str,
) -> PolicyDraft | AmbiguousResponse:

    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise CompilerResponseError(
            "Compiler returned invalid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise CompilerResponseError(
            "Compiler response must be a JSON object."
        )

    try:
        if "error" in data:
            return AmbiguousResponse.model_validate(
                data,
                strict=True,
            )

        if "actions" in data:
            return PolicyDraft.model_validate(
                data,
                strict=True,
            )

    except ValidationError as exc:
        raise CompilerResponseError(
            "Compiler response does not match the expected schema."
        ) from exc

    raise CompilerResponseError(
        "Compiler response does not match any supported response format."
    )