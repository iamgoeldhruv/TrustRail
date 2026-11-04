
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field


class MCPTool(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)


class MCPDiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    server_id: str
    server_revision: str
    tools: list[MCPTool]
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class OtariMCPError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


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
