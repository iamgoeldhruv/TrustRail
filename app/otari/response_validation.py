from typing import Any


def _is_valid_completion(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    choice = choices[0]
    if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
        return False
    message = choice["message"]
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        return False

    tool_calls = message.get("tool_calls")
    if tool_calls is None:
        return isinstance(content, str)
    if not isinstance(tool_calls, list) or not tool_calls:
        return False
    for call in tool_calls:
        if not isinstance(call, dict):
            return False
        if not isinstance(call.get("id"), str) or not isinstance(call.get("type"), str):
            return False
        function = call.get("function")
        if (
            not isinstance(function, dict)
            or not isinstance(function.get("name"), str)
            or not isinstance(function.get("arguments"), str)
        ):
            return False
    return content is None or isinstance(content, str)
