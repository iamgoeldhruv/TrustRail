
import asyncio

from mcp_github.client import GitHubClient
from mcp_github.config import GitHubSettings


async def main() -> None:
    settings = GitHubSettings()

    print(f"Testing GitHub repository: {settings.mcp_github_repo}")

    async with GitHubClient(settings=settings) as client:
        # Test 1: List open issues
        print("\n[1] Fetching open issues...")

        issues = await client.list_issues(state="open")

        print(f"Successfully retrieved {len(issues)} issues.")

        for issue in issues[:5]:
            print(
                f"  #{issue.number}: {issue.title} "
                f"(state={issue.state})"
            )

        # Test 2: Retrieve a specific issue
        if not issues:
            print("\nNo open issues found. Skipping get_issue test.")
            return

        issue_number = issues[0].number

        print(f"\n[2] Fetching issue #{issue_number}...")

        issue = await client.get_issue(issue_number)

        print("Successfully retrieved issue details:")
        print(f"  Number: {issue.number}")
        print(f"  Title: {issue.title}")
        print(f"  State: {issue.state}")
        print(f"  Labels: {[label.name for label in issue.labels]}")
        print(f"  Created: {issue.created_at}")
        print(f"  Updated: {issue.updated_at}")

        print("\nGitHub REST API smoke test PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
