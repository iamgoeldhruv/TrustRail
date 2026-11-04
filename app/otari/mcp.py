
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field


class MCPTool(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] |None=None


class MCPDiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    server_id: str
    server_revision: str
    tools: list[MCPTool]
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class MCPExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    content: list[dict[str, Any]] = Field(default_factory=list)
    isError: bool = False
    structuredContent: dict[str, Any] | None = None


class OtariMCPError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        code: str | None = None,
        execution_state: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)

        self.status_code = status_code
        self.code = code
        self.execution_state = execution_state
        self.request_id = request_id


class OtariMCPClient:

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
        )

    async def discover(
        self,
        server_id: str,
    ) -> MCPDiscoveryResponse:

        if not server_id.strip():
            raise ValueError("MCP server ID cannot be empty")

        encoded_id = quote(server_id, safe="")
        path = f"mcp/servers/{encoded_id}/tools"

        try:
            response = await self._client.get(path)
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            raise OtariMCPError(
                message=(
                    f"Otari discovery failed with HTTP "
                    f"{exc.response.status_code}: {exc.response.text}"
                ),
                status_code=exc.response.status_code,
            ) from exc

        except httpx.RequestError as exc:
            raise OtariMCPError(
                message=f"Could not connect to Otari: {exc}"
            ) from exc

        try:
            return MCPDiscoveryResponse.model_validate(
                response.json()
            )
        except Exception as exc:
            raise OtariMCPError(
                message=f"Invalid Otari discovery response: {exc}"
            ) from exc

    async def execute(
        self,
        *,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        server_revision: str,
        client_execution_id: UUID,
    ) -> MCPExecutionResponse:

        if not server_id.strip():
            raise ValueError("MCP server ID cannot be empty")

        if not tool_name.strip():
            raise ValueError("MCP tool name cannot be empty")

        if len(tool_name) > 256:
            raise ValueError("MCP tool name cannot exceed 256 characters")

        if not server_revision.strip():
            raise ValueError("MCP server revision cannot be empty")

        payload = {
            "mcp_server_id": server_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "server_revision": server_revision,
            "client_execution_id": str(client_execution_id),
        }

        try:
            response = await self._client.post(
                "mcp/execute",
                json=payload,
            )

        except httpx.RequestError as exc:
            raise OtariMCPError(
                message=f"Otari MCP execution outcome is unknown: {exc}",
                execution_state="outcome_unknown",
            ) from exc

        request_id = response.headers.get("Otari-Request-ID")

        if not response.is_success:
            try:
                error_body = response.json()
            except ValueError:
                error_body = {}

            if not isinstance(error_body, dict):
                error_body = {}

            detail = error_body.get("detail")
            message = (
                detail
                if isinstance(detail, str)
                else f"Otari MCP execution failed with HTTP "
                     f"{response.status_code}"
            )

            raise OtariMCPError(
                message=message,
                status_code=response.status_code,
                code=error_body.get("code"),
                execution_state=error_body.get("execution_state"),
                request_id=error_body.get("request_id") or request_id,
            )

        try:
            result = response.json()

            return MCPExecutionResponse.model_validate(result)

        except Exception as exc:
            raise OtariMCPError(
                message=f"Invalid Otari MCP execution response: {exc}",
                status_code=response.status_code,
                execution_state="outcome_unknown",
                request_id=request_id,
            ) from exc

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OtariMCPClient":
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        await self.aclose()
