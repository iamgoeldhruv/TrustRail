from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]


class MCPToolDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] | None = None


class MCPExecutionRequest(BaseModel):
    mcp_server_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    server_revision: str
    client_execution_id: str
