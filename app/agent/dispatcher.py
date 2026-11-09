
import inspect
import json
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent.models import GetIssueArgs, ListIssuesArgs, ProposeCloseArgs
from app.agent.tool_handlers import AgentToolError, AgentToolHandlers
from app.ledger.models import LedgerEventCreate
from app.ledger.store import LedgerStore

# This is the complete set of tools the model is allowed to invoke.
# Never add close_issue_with_note here.
ALLOWED_AGENT_TOOLS = frozenset({
    "list_issues",
    "get_issue",
    "propose_close",
})

READ_ONLY_TOOLS = frozenset({
    "list_issues",
    "get_issue",
})

MAX_ARGUMENTS_LENGTH = 16_384


class AgentToolDispatcher:
    """Dispatches model-requested tools to approved TrustRail handlers."""

    def __init__(
        self,
        handlers: AgentToolHandlers,
        ledger: LedgerStore,
    ) -> None:
        self.handlers = handlers
        self.ledger = ledger

    async def _record_read_event(
        self,
        *,
        run_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        outcome: str,
        error_code: str | None = None,
    ) -> bool:
        """Persist a lightweight audit event for a read-tool invocation."""

        payload: dict[str, Any] = {
            "tool_name": tool_name,
            "arguments": arguments,
            "outcome": outcome,
        }

        if error_code is not None:
            payload["error"] = {"code": error_code}

        try:
            self.ledger.append_event(
                LedgerEventCreate(
                    run_id=run_id,
                    type="READ_TOOL_CALL",
                    payload=payload,
                )
            )
            return True
        except Exception:
            # Do not expose database details or retry the external read.
            return False

    async def _dispatch_read_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        """Execute a read tool and record its outcome."""

        try:
            result: Any = getattr(self.handlers, tool_name)(arguments)

            if inspect.isawaitable(result):
                result = await result

        except AgentToolError:
            logged = await self._record_read_event(
                run_id=run_id,
                tool_name=tool_name,
                arguments=arguments,
                outcome="FAILED",
                error_code="tool_execution_error",
            )

            if not logged:
                return {
                    "error": {
                        "code": "audit_logging_error",
                        "message": (
                            "The read operation failed and its audit event "
                            "could not be persisted."
                        ),
                    }
                }

            return {
                "error": {
                    "code": "tool_execution_error",
                    "message": "The requested read operation failed.",
                }
            }

        except Exception:
            logged = await self._record_read_event(
                run_id=run_id,
                tool_name=tool_name,
                arguments=arguments,
                outcome="FAILED",
                error_code="internal_tool_error",
            )

            if not logged:
                return {
                    "error": {
                        "code": "audit_logging_error",
                        "message": (
                            "The read operation failed and its audit event "
                            "could not be persisted."
                        ),
                    }
                }

            return {
                "error": {
                    "code": "internal_tool_error",
                    "message": "An unexpected error occurred during the read.",
                }
            }

        logged = await self._record_read_event(
            run_id=run_id,
            tool_name=tool_name,
            arguments=arguments,
            outcome="SUCCEEDED",
        )

        if not logged:
            return {
                "error": {
                    "code": "audit_logging_error",
                    "message": (
                        "The read operation completed, but its audit event "
                        "could not be persisted. Do not retry automatically."
                    ),
                }
            }

        return result

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
            validated_arguments = validators[tool_name].model_validate(
                arguments
            )
        except ValidationError as exc:
            raise AgentToolError(
                f"Invalid arguments for {tool_name}."
            ) from exc

        if tool_name in READ_ONLY_TOOLS:
            if not isinstance(run_id, str) or not run_id.strip():
                raise AgentToolError(
                    "A valid trusted run_id is required."
                )

            # Use validated arguments, not the original model-generated JSON.
            safe_arguments = validated_arguments.model_dump(
                mode="json",
                exclude_none=True,
            )

            return await self._dispatch_read_tool(
                tool_name=tool_name,
                arguments=safe_arguments,
                run_id=run_id.strip(),
            )

        if tool_name == "propose_close":
            if not isinstance(run_id, str) or not run_id.strip():
                raise AgentToolError(
                    "A valid trusted run_id is required."
                )

            try:
                result = self.handlers.propose_close(
                    arguments=validated_arguments.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    run_id=run_id.strip(),
                )

                if inspect.isawaitable(result):
                    result = await result

            except AgentToolError as exc:
                return {
                    "error": {
                        "code": "tool_execution_error",
                        "message": str(exc),
                    }
                }

            return result

        # Defensive fallback: adding a tool to the allowlist must not
        # accidentally make it executable without an explicit handler.
        raise AgentToolError(
            f"No handler is registered for {tool_name!r}."
        )
