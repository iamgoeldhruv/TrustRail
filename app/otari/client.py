
from typing import Any

import httpx

from app.core.config import settings
from app.otari.exceptions import (
    OtariAPIError,
    OtariAuthenticationError,
    OtariConnectionError,
    OtariResponseError,
    OtariTimeoutError,
)
from app.otari.response_validation import _is_valid_completion


class OtariClient:

    def __init__(self,*,api_key: str | None = None):
        self.base_url = settings.otari_base_url.rstrip("/")
        self.api_key = api_key or settings.otari_api_key
        self.timeout = settings.otari_timeout

        self.http_client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        self.http_client.headers["Authorization"] = "Bearer " + self.api_key

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> dict:

        url = f"{self.base_url}/chat/completions"

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if max_tokens is not None:
            if max_tokens < 1:
                raise ValueError("max_tokens must be positive")
            payload["max_tokens"] = max_tokens

        try:
            response = await self.http_client.post(
                url,
                json=payload,
            )

            if response.status_code == 401:
                raise OtariAuthenticationError(
                    "Otari rejected the API key."
                )

            _=response.raise_for_status()

        except httpx.TimeoutException as exc:
            raise OtariTimeoutError(
                "Request to Otari timed out."
            ) from exc

        except httpx.ConnectError as exc:
            raise OtariConnectionError(
                "Could not connect to Otari."
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise OtariAPIError(
                message=f"Otari returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc

        try:
            data = response.json()

        except ValueError as exc:
            raise OtariResponseError(
                "Otari returned invalid JSON."
            ) from exc

        if not _is_valid_completion(data):
            raise OtariResponseError(
                "Otari returned an unexpected chat completion response."
            )

        return data

    async def aclose(self) -> None:
        await self.http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.aclose()