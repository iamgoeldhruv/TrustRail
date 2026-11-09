import asyncio
import json
import logging
import os
import re

import httpx

from mcp_github.client import GitHubClient
from mcp_github.config import GitHubSettings


logger = logging.getLogger("trustrail.demo_reset")


# The inactivity values must match scripts/seed_sandbox.py.
SEED_ISSUES = {
    "issue-01": 45,
    "issue-02": 60,
    "issue-03": 12,
    "issue-04": 90,
    "issue-05": 50,
    "issue-06": 70,
    "issue-07": 55,
    "issue-08": 40,
    "issue-09": 35,
    "issue-10": 80,
}


TRANSACTION_MARKER_PATTERN = re.compile(
    r"<!--\s*trustrail:txn=[A-Za-z0-9_-]{1,128}\s*-->"
)


def find_seeded_issues(issues: list) -> dict[str, int]:
    """
    Find seeded issues using their unique seed markers.

    Returns:
        Mapping of seed key to actual GitHub issue number.
    """

    seeded: dict[str, int] = {}

    for issue in issues:
        body = issue.body or ""

        for seed_key in SEED_ISSUES:
            marker = f"<!-- trustrail-seed:{seed_key} -->"

            if marker not in body:
                continue

            if seed_key in seeded:
                raise RuntimeError(
                    f"Duplicate seed marker found: {seed_key}. "
                    "Resolve duplicate issues manually before resetting."
                )

            seeded[seed_key] = issue.number

    missing = set(SEED_ISSUES) - set(seeded)

    if missing:
        raise RuntimeError(
            "Cannot safely reset sandbox. "
            f"Missing seeded issues: {sorted(missing)}"
        )

    return seeded


async def reset_issue(
    client: GitHubClient,
    issue_number: int,
) -> None:
    """Reopen an issue and remove TrustRail transaction comments."""

    issue = await client.get_issue(issue_number)

    if issue.state == "closed":
        await client.reopen_issue(issue_number)

        logger.info(
            "Reopened issue #%s",
            issue_number,
        )
    else:
        logger.info(
            "Issue #%s is already open",
            issue_number,
        )

    comments = await client.get_issue_comments(issue_number)

    deleted_count = 0

    for comment in comments:
        body = comment.body or ""

        if not TRANSACTION_MARKER_PATTERN.search(body):
            continue

        await client.delete_issue_comment(
            issue_number=issue_number,
            comment_id=comment.id,
        )

        deleted_count += 1

        logger.info(
            "Deleted TrustRail transaction comment %s from issue #%s",
            comment.id,
            issue_number,
        )

    logger.info(
        "Issue #%s reset: removed %s transaction comments",
        issue_number,
        deleted_count,
    )


def restore_demo_ages(
    settings: GitHubSettings,
    issue_numbers: dict[str, int],
) -> None:
    """Restore inactivity overrides using actual GitHub issue numbers."""

    demo_ages = {
        str(issue_numbers[seed_key]): inactive_days
        for seed_key, inactive_days in SEED_ISSUES.items()
    }

    path = settings.demo_ages_file
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_name(f".{path.name}.tmp")

    temp_path.write_text(
        json.dumps(demo_ages, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    temp_path.replace(path)

    logger.info(
        "Restored demo inactivity overrides in %s",
        path,
    )


async def reset_fault_mode(
    settings: GitHubSettings,
) -> None:
    """
    Reset the GitHub MCP server fault mode to 'none'.

    Configure MCP_GITHUB_SERVER_URL with the public server base URL.
    """

    server_url = os.getenv("MCP_GITHUB_SERVER_URL", "").strip() 

    if not server_url:
        raise RuntimeError(
            "MCP_GITHUB_SERVER_URL is not configured. "
            "Set it to the public GitHub MCP server base URL."
        )

    endpoint = f"{server_url.rstrip('/')}/admin/fault"

    token = settings.trustrail_admin_token.get_secret_value()

    try:
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            response = await http_client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                json={"mode": "none"},
            )

            response.raise_for_status()

            result = response.json()

    except httpx.TimeoutException as exc:
        raise RuntimeError(
            "Timed out while resetting MCP fault mode."
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            "MCP fault reset failed with HTTP "
            f"{exc.response.status_code}: {exc.response.text}"
        ) from exc

    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not connect to GitHub MCP server: {exc}"
        ) from exc

    if result.get("mode") != "none" or result.get("updated") is not True:
        raise RuntimeError(
            f"Unexpected fault reset response: {result}"
        )

    logger.info("MCP fault mode reset to none")


async def verify_reset(
    client: GitHubClient,
    issue_numbers: dict[str, int],
) -> None:
    """Verify that all seeded issues are open and transaction comments are gone."""

    for issue_number in issue_numbers.values():
        issue = await client.get_issue(issue_number)

        if issue.state != "open":
            raise RuntimeError(
                f"Issue #{issue_number} is not open after reset."
            )

        comments = await client.get_issue_comments(issue_number)

        remaining_markers = [
            comment.id
            for comment in comments
            if TRANSACTION_MARKER_PATTERN.search(comment.body or "")
        ]

        if remaining_markers:
            raise RuntimeError(
                f"Issue #{issue_number} still contains "
                f"TrustRail transaction comments: {remaining_markers}"
            )

    logger.info(
        "Verified all %s seeded issues are open "
        "and contain no TrustRail transaction comments.",
        len(issue_numbers),
    )


async def demo_reset() -> None:
    settings = GitHubSettings()

    logger.info(
        "Starting TrustRail demo reset for repository %s",
        settings.mcp_github_repo,
    )
    await reset_fault_mode(settings)

    async with GitHubClient(settings=settings) as client:
        # 1. Find all seeded issues.
        issues = await client.list_issues(state="all")

        issue_numbers = find_seeded_issues(issues)

        logger.info(
            "Found all %s seeded issues.",
            len(issue_numbers),
        )

        # 2. Reopen issues and delete transaction comments.
        for seed_key, issue_number in issue_numbers.items():
            logger.info(
                "Resetting %s (GitHub issue #%s)",
                seed_key,
                issue_number,
            )

            await reset_issue(
                client=client,
                issue_number=issue_number,
            )

        # 3. Restore deterministic inactivity overrides.
        restore_demo_ages(
            settings=settings,
            issue_numbers=issue_numbers,
        )

        # 4. Verify GitHub state.
        await verify_reset(
            client=client,
            issue_numbers=issue_numbers,
        )

    # 5. Reset MCP fault injection.
    await reset_fault_mode(settings)

    logger.info("TrustRail demo sandbox reset completed successfully.")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(demo_reset())


if __name__ == "__main__":
    main()