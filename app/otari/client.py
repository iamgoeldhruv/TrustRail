
from typing import Any

import httpx

from app.core.config import settings
from app.otari.exceptions import (
    OtariAPIError,
    OtariAuthenticationError,
    OtariConnectionError,
    OtariGuardrailBlockedError,
    OtariGuardrailUnavailableError,
    OtariResponseError,
    OtariTimeoutError,
)
from app.otari.guardrails import OtariGuardrailResult, parse_guardrail_header
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

        _, data, _ = await self._chat_completion_request(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
        )
        return data

    async def chat_completion_with_metadata(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> tuple[dict[str, Any], list[OtariGuardrailResult]]:
        _, data, guardrails = await self._chat_completion_request(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
        )
        return data, guardrails

    async def _chat_completion_request(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
        max_tokens: int | None,
    ) -> tuple[httpx.Response, dict[str, Any], list[OtariGuardrailResult]]:
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

            if response.status_code >= 400:
                body: Any = {}
                if response.headers.get("content-type", "").startswith("application/json"):
                    try:
                        body = response.json()
                    except ValueError:
                        body = {}
                code = body.get("code") if isinstance(body, dict) else None
                request_id = response.headers.get("Otari-Request-ID")
                if code == "guardrail_violation":
                    raise OtariGuardrailBlockedError(
                        "Otari blocked the planner inference.",
                        status_code=response.status_code,
                        code=code,
                        request_id=request_id,
                    )
                if (
                    response.status_code == 502
                    and isinstance(code, str)
                    and code.startswith("guardrail_")
                ):
                    raise OtariGuardrailUnavailableError(
                        "Otari could not evaluate the mandatory guardrail.",
                        status_code=response.status_code,
                        code=code,
                        request_id=request_id,
                    )
                response.raise_for_status()

        except httpx.TimeoutException as exc:
            raise OtariTimeoutError(
                "Request to Otari timed out."
            ) from exc

        except httpx.ConnectError as exc:
            raise OtariConnectionError(
                "Could not connect to Otari."
            ) from exc

        except httpx.HTTPStatusError as exc:
            body = {}
            if exc.response.headers.get("content-type", "").startswith("application/json"):
                try:
                    parsed = exc.response.json()
                    body = parsed if isinstance(parsed, dict) else {}
                except ValueError:
                    body = {}
            raise OtariAPIError(
                message=f"Otari returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                code=body.get("code") if isinstance(body.get("code"), str) else None,
                request_id=exc.response.headers.get("Otari-Request-ID"),
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

        guardrails = parse_guardrail_header(response.headers.get("Otari-Guardrails"))
        return response, data, guardrails

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """GET a JSON resource from the configured Otari v1 API."""
        base = self.base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        url = f"{base}/{path.lstrip('/')}"

        try:
            response = await self.http_client.get(url, params=params)
            if response.status_code == 401:
                raise OtariAuthenticationError("Otari rejected the API key.")
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OtariTimeoutError("Request to Otari timed out.") from exc
        except httpx.ConnectError as exc:
            raise OtariConnectionError("Could not connect to Otari.") from exc
        except httpx.HTTPStatusError as exc:
            raise OtariAPIError(
                message=f"Otari returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                request_id=exc.response.headers.get("Otari-Request-ID"),
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise OtariResponseError("Otari returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise OtariResponseError("Otari returned an unexpected JSON response.")
        return data

    async def aclose(self) -> None:
        await self.http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.aclose()