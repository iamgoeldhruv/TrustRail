
import asyncio

from app.core.config import settings
from app.otari.client import OtariClient
from app.otari.exceptions import OtariError


async def ping_command() -> int:

    model = settings.tr_planner_model

    print("TrustRail: checking Otari connectivity...")
    print(f"Model: {model}")

    try:
        async with OtariClient() as client:
            response = await client.chat_completion(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Reply with exactly: "
                            "TrustRail connection successful."
                        ),
                    }
                ],
            )

        content = response["choices"][0]["message"]["content"]

        print("\nOtari connection successful.")
        print(f"Model response: {content}")

        return 0

    except OtariError as exc:
        print(f"\nOtari connection failed: {exc}")
        return 1

    except Exception as exc:
        print(f"\nUnexpected error: {exc}")
        return 1
