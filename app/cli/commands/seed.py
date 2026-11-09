import asyncio
import logging

from scripts.seed_sandbox import seed_sandbox


async def seed_command() -> int:
    try:
        await seed_sandbox()
        print("TrustRail sandbox seeding completed successfully.")
        return 0

    except Exception as exc:
        logging.exception("Sandbox seeding failed")
        print(f"Error seeding sandbox: {exc}")
        return 1


def seed_command_sync() -> int:
    return asyncio.run(seed_command())