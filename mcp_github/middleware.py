import logging
from typing import Any

from mcp_github.fault_injection import (
    mark_response_for_drop,
    reset_response_drop_flag,
    response_drop_requested,
    set_response_drop_flag,
)

logger = logging.getLogger(__name__)


class DropResponseMiddleware:
    """
    Simulates a lost HTTP response after a GitHub write has been applied.

    Buffers the MCP POST response until the application completes.
    If the tool marked this request for dropping, no response is sent
    to the HTTP client.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        token = set_response_drop_flag(False)
        messages: list[dict] = []

        async def buffer_send(message: dict) -> None:
            messages.append(message)

        try:
            await self.app(scope, receive, buffer_send)

            if response_drop_requested():
                logger.warning(
                    "Dropping MCP HTTP response after successful GitHub write."
                )

                # Deliberately terminate the connection without forwarding
                # the response to the client.
                raise ConnectionResetError(
                    "Injected response loss after GitHub write."
                )

            for message in messages:
                await send(message)

        finally:
            reset_response_drop_flag(token)