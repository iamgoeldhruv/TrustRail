from mcp.server import MCPServer
from pydantic import BaseModel
import os


mcp = MCPServer("TrustRail-MCP-Spike")


SERVER_STATE: dict[str, str] = {
    "status": "running",
    "message": "Hello from TrustRail MCP Server",
}


class StatusResponse(BaseModel):
    status: str
    message: str


class UpdateStatusResponse(BaseModel):
    success: bool
    updated_message: str


@mcp.tool()
def get_status() -> StatusResponse:

    return StatusResponse(
        status=SERVER_STATE["status"],
        message=SERVER_STATE["message"],
    )


@mcp.tool()
def update_status(message: str) -> UpdateStatusResponse:

    normalized_message = message.strip()

    if not normalized_message:
        raise ValueError("Status message cannot be empty.")

    if len(normalized_message) > 200:
        raise ValueError("Status message cannot exceed 200 characters.")

    SERVER_STATE["message"] = normalized_message

    return UpdateStatusResponse(
        success=True,
        updated_message=SERVER_STATE["message"],
    )


def main() -> None:
   

    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))

    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
