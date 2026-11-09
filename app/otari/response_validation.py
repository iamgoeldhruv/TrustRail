
from typing import Any


def _is_valid_completion(data: Any) -> bool:
    if not isinstance(data, dict):
        return False

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return False

    choice = choices[0]
    if not isinstance(choice, dict):
        return False

    message = choice.get("message")
    if not isinstance(message, dict):
        return False

    content = message.get("content")
    if content is not None and not isinstance(content, str):
        return False

    tool_calls = message.get("tool_calls")

    # No tool calls: a text response is valid.
    if tool_calls is None or tool_calls == []:
        return isinstance(content, str)

    if not isinstance(tool_calls, list):
        return False

    for call in tool_calls:
        if not isinstance(call, dict):
            return False

        if not isinstance(call.get("id"), str):
            return False

        if not isinstance(call.get("type"), str):
            return False

        function = call.get("function")
        if (
            not isinstance(function, dict)
            or not isinstance(function.get("name"), str)
            or not isinstance(function.get("arguments"), str)
        ):
            return False

    return content is None or isinstance(content, str)
