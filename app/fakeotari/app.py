from __future__ import annotations

import os
from typing import Any

import httpx
import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.fakeotari.models import ChatCompletionRequest, MCPExecutionRequest
from app.fakeotari.outcomes import ExecutionOutcome
from app.fakeotari.state import FakeOtariState


def _mcp_text(value: Any) -> list[dict[str, str]]:
    return [{"type": "text", "text": str(value)}]


def create_app(state: FakeOtariState | None = None) -> FastAPI:
    fake_state = state or FakeOtariState()
    app = FastAPI(title="Fake Otari")
    app.state.fake_otari = fake_state
    router = APIRouter(prefix="/api/v1")

    @router.post("/chat/completions")
    async def chat_completions(request: ChatCompletionRequest) -> dict[str, Any]:
        return fake_state.chat_response()

    @router.get("/mcp/servers/{server_id}/tools")
    async def discover_tools(server_id: str) -> dict[str, Any]:
        if server_id != fake_state.server_id:
            raise HTTPException(status_code=404, detail="MCP server not found")
        return {
            "server_id": fake_state.server_id,
            "server_revision": fake_state.server_revision,
            "tools": [tool.model_dump(by_alias=True) for tool in fake_state.tools],
            "warnings": [],
        }

    @router.post("/mcp/execute", response_model=None)
    async def execute(request: MCPExecutionRequest) -> Any:
        if request.mcp_server_id != fake_state.server_id:
            raise HTTPException(status_code=404, detail="MCP server not found")

        outcome = fake_state.take_next_outcome()
        request_data = request.model_dump()
        fake_state.record_request(request_data, outcome)

        if outcome is ExecutionOutcome.CONFLICT or (
            request.server_revision != fake_state.server_revision
        ):
            return JSONResponse(
                status_code=409,
                headers={"Otari-Request-ID": request.client_execution_id},
                content={
                    "detail": "MCP server revision has changed",
                    "code": "mcp_server_changed",
                    "execution_state": "not_started",
                    "request_id": request.client_execution_id,
                },
            )

        tool_names = {tool.name for tool in fake_state.tools}
        if request.tool_name not in tool_names:
            raise HTTPException(status_code=404, detail="MCP tool not found")

        if outcome is ExecutionOutcome.NOT_STARTED:
            return {
                "content": _mcp_text("Tool execution did not start"),
                "isError": True,
                "execution_state": "not_started",
            }

        try:
            result = fake_state.invoke(request.tool_name, request.arguments)
        except ValueError as exc:
            return {"content": _mcp_text(str(exc)), "isError": True}

        if outcome is ExecutionOutcome.OUTCOME_UNKNOWN:
            raise httpx.ReadError("Simulated lost response after tool execution")

        if outcome is ExecutionOutcome.IS_ERROR:
            return {
                "content": _mcp_text("Fake tool returned an error"),
                "isError": True,
            }

        return {
            "content": _mcp_text(result),
            "isError": False,
            "structuredContent": result,
        }

    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "app.fakeotari.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8001")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
