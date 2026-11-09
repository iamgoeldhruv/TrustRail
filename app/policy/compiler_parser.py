import json

from pydantic import ValidationError

from app.policy.compiler_models import (
    AmbiguousResponse,
    PolicyDraft,
)


class CompilerResponseError(ValueError):
    """Raised when the LLM returns an invalid compiler response."""
def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}

    for key, value in pairs:
        if key in result:
            raise CompilerResponseError(
                f"Compiler returned duplicate JSON key: {key}"
            )
        result[key] = value

    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise CompilerResponseError(
        f"Compiler returned non-standard JSON constant: {value}"
    )

def parse_compiler_response(
    raw_response: str,
) -> PolicyDraft | AmbiguousResponse:

    try:
        data = json.loads(
            raw_response,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
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