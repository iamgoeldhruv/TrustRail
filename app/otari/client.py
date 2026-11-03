
import httpx

from app.core.config import settings
from app.otari.exceptions import (
    OtariAPIError,
    OtariAuthenticationError,
    OtariConnectionError,
    OtariResponseError,
    OtariTimeoutError,
)


class OtariClient:

    def __init__(self):
        self.base_url = settings.otari_base_url.rstrip("/")
        self.api_key = settings.otari_api_key
        self.timeout = settings.otari_timeout

        self.http_client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
    ) -> dict:

        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
        }

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

        if (
            not isinstance(data, dict)
            or not isinstance(data.get("choices"), list)
            or not data["choices"]
            or not isinstance(data["choices"][0], dict)
            or not isinstance(data["choices"][0].get("message"), dict)
            or not isinstance(data["choices"][0]["message"].get("content"), str)
        ):
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