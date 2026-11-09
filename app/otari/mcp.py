from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)

from app.otari.exceptions import (
    OtariExecutionState,
    OtariMCPError,
    OtariMCPErrorBody,
    OtariMCPErrorCode,
    OtariMCPNotStartedError,
    OtariMCPOutcomeUnknownError,
    OtariMCPResponseError,
    OtariMCPServerChangedError,
)


class MCPTool(BaseModel):
    """A tool exposed by a registered MCP server."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] | None = None


class MCPDiscoveryResponse(BaseModel):
    """Response returned by Otari MCP tool discovery."""

    model_config = ConfigDict(extra="allow")

    server_id: str
    server_revision: str
    tools: list[MCPTool]
    warnings: list[dict[str, Any]] = Field(default_factory=list)

    # HTTP response metadata, not part of the Otari JSON body.
    otari_request_id: str | None = Field(
        default=None,
        exclude=True,
    )


class MCPExecutionResponse(BaseModel):
    """Native MCP execution result returned by Otari."""

    model_config = ConfigDict(extra="allow")

    content: list[dict[str, Any]] = Field(default_factory=list)
    isError: bool = False
    structuredContent: dict[str, Any] | None = None

    # HTTP response metadata, not part of the native MCP result.
    otari_request_id: str | None = Field(
        default=None,
        exclude=True,
    )


class OtariMCPClient:
    """
    Async client for Otari caller-orchestrated MCP endpoints.

    Responsibilities:
    - Discover tools exposed by a registered MCP server.
    - Execute an explicitly authorized MCP tool call.
    - Parse Otari's shared error response.
    - Preserve Otari request IDs.
    - Classify execution certainty conservatively.

    Important:
    POST /mcp/execute is called exactly once.
    This client does not implement automatic retries.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 60.0,
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
        self._client.headers["Authorization"] = "Bearer " + api_key

    @staticmethod
    def _parse_error_response(
        response: httpx.Response,
        *,
        execution_request: bool,
    ) -> OtariMCPError:
        """
        Parse Otari's shared MCP error response.

        Both discovery and execution endpoints use the same
        JSON error structure.

        Header and body request IDs are preserved separately.

        If an execution error response cannot be parsed,
        its outcome is classified as unknown.
        """

        header_request_id = response.headers.get("Otari-Request-ID")
        retry_after = response.headers.get("Retry-After")

        try:
            error_body = OtariMCPErrorBody.model_validate_json(response.content)

        except (ValueError, ValidationError, TypeError):
            message = f"Otari returned an invalid MCP error response (HTTP {response.status_code})."

            if execution_request:
                return OtariMCPOutcomeUnknownError(
                    message=message,
                    status_code=response.status_code,
                    execution_state="outcome_unknown",
                    header_request_id=header_request_id,
                    retry_after=retry_after,
                )

            return OtariMCPResponseError(
                message=message,
                status_code=response.status_code,
                header_request_id=header_request_id,
                retry_after=retry_after,
            )

        common = {
            "message": error_body.detail,
            "status_code": response.status_code,
            "code": error_body.code.value,
            "execution_state": error_body.execution_state.value,
            "body_request_id": error_body.request_id,
            "header_request_id": header_request_id,
            "retry_after": retry_after,
        }

        # A stale server revision invalidates the approval.
        if error_body.code == OtariMCPErrorCode.MCP_SERVER_CHANGED:
            return OtariMCPServerChangedError(**common)

        # Otari explicitly reports that dispatch started
        # but no definitive result was returned.
        if error_body.execution_state == OtariExecutionState.OUTCOME_UNKNOWN:
            return OtariMCPOutcomeUnknownError(**common)

        # Otari confirms that dispatch did not start.
        if error_body.execution_state == OtariExecutionState.NOT_STARTED:
            return OtariMCPNotStartedError(**common)

        # Defensive fallback.
        if execution_request:
            return OtariMCPOutcomeUnknownError(
                message=error_body.detail,
                status_code=response.status_code,
                code=error_body.code.value,
                execution_state="outcome_unknown",
                body_request_id=error_body.request_id,
                header_request_id=header_request_id,
                retry_after=retry_after,
            )

        return OtariMCPError(**common)

    async def discover(
        self,
        server_id: str,
    ) -> MCPDiscoveryResponse:
        """
        Discover tools exposed by a registered Otari MCP server.

        Returns:
            MCPDiscoveryResponse containing:
            - server_id
            - server_revision
            - tools
            - warnings
            - Otari response request ID
        """

        if not server_id.strip():
            raise ValueError("MCP server ID cannot be empty")

        encoded_id = quote(server_id, safe="")

        path = f"mcp/servers/{encoded_id}/tools"

        try:
            response = await self._client.get(path)

        except httpx.RequestError as exc:
            raise OtariMCPError(
                message=f"Could not connect to Otari: {exc}",
            ) from exc

        if not response.is_success:
            raise self._parse_error_response(
                response,
                execution_request=False,
            )

        try:
            discovery = MCPDiscoveryResponse.model_validate(response.json())

        except (ValueError, ValidationError, TypeError) as exc:
            raise OtariMCPResponseError(
                message=("Otari returned an invalid MCP discovery response."),
                status_code=response.status_code,
                header_request_id=response.headers.get("Otari-Request-ID"),
            ) from exc

        return discovery.model_copy(
            update={"otari_request_id": response.headers.get("Otari-Request-ID")}
        )

    async def execute(
        self,
        *,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        server_revision: str,
        client_execution_id: UUID,
    ) -> MCPExecutionResponse:
        """
        Execute one MCP tool call through Otari.

        IMPORTANT:
        Exactly one HTTP request is sent.

        A network failure or ambiguous response is classified
        as outcome_unknown. The caller must not automatically
        retry this operation.
        """

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
            # Exactly one execution attempt.
            response = await self._client.post(
                "mcp/execute",
                json=payload,
            )

        except httpx.RequestError as exc:
            raise OtariMCPOutcomeUnknownError(
                message=(
                    "Otari execution request failed without a "
                    "definitive response. The operation may have executed."
                ),
                execution_state="outcome_unknown",
            ) from exc

        if not response.is_success:
            raise self._parse_error_response(
                response,
                execution_request=True,
            )

        try:
            result = MCPExecutionResponse.model_validate(response.json())

        except (ValueError, ValidationError, TypeError) as exc:
            raise OtariMCPOutcomeUnknownError(
                message=(
                    "Otari returned an invalid execution response. The operation may have executed."
                ),
                status_code=response.status_code,
                execution_state="outcome_unknown",
                header_request_id=response.headers.get("Otari-Request-ID"),
            ) from exc

        return result.model_copy(
            update={"otari_request_id": response.headers.get("Otari-Request-ID")}
        )

    async def aclose(self) -> None:
        """Close the underlying HTTPX client."""

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
