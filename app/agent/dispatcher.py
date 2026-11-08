import inspect
import json
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent.models import GetIssueArgs, ListIssuesArgs, ProposeCloseArgs
from app.agent.tool_handlers import AgentToolError, AgentToolHandlers

# This is the complete set of tools the model is allowed to invoke.
# Never add close_issue_with_note here.
ALLOWED_AGENT_TOOLS = frozenset({
    "list_issues",
    "get_issue",
    "propose_close",
})

MAX_ARGUMENTS_LENGTH = 16_384


class AgentToolDispatcher:
    """Dispatches model-requested tools to approved TrustRail handlers."""

    def __init__(self, handlers: AgentToolHandlers) -> None:
        self.handlers = handlers

    async def dispatch(
        self,
        *,
        tool_name: str,
        arguments_json: str,
        run_id: str,
    ) -> dict[str, Any]:
        """Validate and execute one model-requested tool call."""

        if tool_name not in ALLOWED_AGENT_TOOLS:
            raise AgentToolError(
                f"Tool {tool_name!r} is not permitted."
            )

        if not isinstance(arguments_json, str):
            raise AgentToolError(
                "Tool arguments must be a JSON string."
            )

        if len(arguments_json) > MAX_ARGUMENTS_LENGTH:
            raise AgentToolError(
                "Tool arguments exceed the maximum allowed size."
            )

        try:
            arguments = json.loads(arguments_json)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AgentToolError(
                "Tool arguments contain invalid JSON."
            ) from exc

        if not isinstance(arguments, dict):
            raise AgentToolError(
                "Tool arguments must be a JSON object."
            )

        validators: dict[str, type[BaseModel]] = {
            "list_issues": ListIssuesArgs,
            "get_issue": GetIssueArgs,
            "propose_close": ProposeCloseArgs,
        }
        try:
            validators[tool_name].model_validate(arguments)
        except ValidationError as exc:
            raise AgentToolError(
                f"Invalid arguments for {tool_name}."
            ) from exc

        if tool_name == "list_issues":
            result: Any
            try:
                result = self.handlers.list_issues(arguments)
                if inspect.isawaitable(result):
                    result = await result
            except AgentToolError as exc:
                return {"error": {"code": "tool_execution_error", "message": str(exc)}}
            return result

        if tool_name == "get_issue":
            try:
                result = self.handlers.get_issue(arguments)
                if inspect.isawaitable(result):
                    result = await result
            except AgentToolError as exc:
                return {"error": {"code": "tool_execution_error", "message": str(exc)}}
            return result

        if tool_name == "propose_close":
            if not isinstance(run_id, str) or not run_id.strip():
                raise AgentToolError(
                    "A valid trusted run_id is required."
                )

            try:
                result = self.handlers.propose_close(
                    arguments=arguments,
                    run_id=run_id,
                )
                if inspect.isawaitable(result):
                    result = await result
            except AgentToolError as exc:
                return {"error": {"code": "tool_execution_error", "message": str(exc)}}
            return result

        # Defensive fallback: adding a tool to the allowlist must not
        # accidentally make it executable without an explicit handler.
        raise AgentToolError(
            f"No handler is registered for {tool_name!r}."
        )
