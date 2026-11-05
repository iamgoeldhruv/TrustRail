from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from app.fakeotari.models import MCPToolDefinition
from app.fakeotari.outcomes import ExecutionOutcome

DEFAULT_TOOLS = [
    MCPToolDefinition(
        name="get_status",
        description="Read the current fake Otari status.",
        input_schema={"type": "object", "properties": {}},
        annotations={"readOnlyHint": True},
    ),
    MCPToolDefinition(
        name="update_status",
        description="Update the fake Otari status message.",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        annotations={"readOnlyHint": False},
    ),
]


class FakeOtariState:
    """Thread-safe state and controls for a fake Otari instance."""

    def __init__(
        self,
        *,
        server_id: str = "fake-server",
        server_revision: str = "revision-1",
        tools: list[MCPToolDefinition] | None = None,
    ) -> None:
        self.server_id = server_id
        self._server_revision = server_revision
        self._tools = deepcopy(tools or DEFAULT_TOOLS)
        self._next_outcome = ExecutionOutcome.SUCCESS
        self._chat_response: dict[str, Any] = {
            "id": "fake-chat-completion",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "fake response"},
                    "finish_reason": "stop",
                }
            ],
        }
        self.execution_request_count = 0
        self.invocation_count = 0
        self.side_effect_count = 0
        self.execution_history: list[dict[str, Any]] = []
        self.status_message = "running"
        self._lock = RLock()

    @property
    def server_revision(self) -> str:
        with self._lock:
            return self._server_revision

    @property
    def tools(self) -> list[MCPToolDefinition]:
        with self._lock:
            return deepcopy(self._tools)

    def set_next_outcome(self, outcome: ExecutionOutcome) -> None:
        with self._lock:
            self._next_outcome = outcome

    def take_next_outcome(self) -> ExecutionOutcome:
        with self._lock:
            outcome = self._next_outcome
            self._next_outcome = ExecutionOutcome.SUCCESS
            return outcome

    def set_server_revision(self, revision: str) -> None:
        with self._lock:
            self._server_revision = revision

    def set_chat_response(self, response: dict[str, Any]) -> None:
        with self._lock:
            self._chat_response = deepcopy(response)

    def chat_response(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._chat_response)

    def reset(self) -> None:
        with self._lock:
            self._next_outcome = ExecutionOutcome.SUCCESS
            self.execution_request_count = 0
            self.invocation_count = 0
            self.side_effect_count = 0
            self.execution_history.clear()
            self.status_message = "running"

    def record_request(self, request: dict[str, Any], outcome: ExecutionOutcome) -> None:
        with self._lock:
            self.execution_request_count += 1
            self.execution_history.append(
                {"request": deepcopy(request), "outcome": outcome.value, "invoked": False}
            )

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.invocation_count += 1
            self.execution_history[-1]["invoked"] = True

            if tool_name == "get_status":
                return {"status": self.status_message}

            if tool_name == "update_status":
                message = arguments.get("message")
                if not isinstance(message, str) or not message.strip():
                    raise ValueError("message must be a non-empty string")
                self.status_message = message.strip()
                self.side_effect_count += 1
                return {"success": True, "status": self.status_message}

            self.side_effect_count += 1
            return {"success": True, "tool": tool_name, "arguments": deepcopy(arguments)}
