
from typing import Any

import httpx

from mcp_github.config import GitHubSettings
from mcp_github.errors import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubConnectionError,
    GitHubNotFoundError,
)
from mcp_github.models import GitHubComment, GitHubIssue

from mcp_github.models import GitHubComment, GitHubIssue, GitHubLabel
class GitHubClient:
    def __init__(
        self,
        settings: GitHubSettings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = http_client is None

        self._client = http_client or httpx.AsyncClient(
            base_url=settings.github_api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": (
                    f"Bearer {settings.mcp_github_pat.get_secret_value()}"
                ),
                "X-GitHub-Api-Version": settings.github_api_version,
            },
            timeout=settings.github_timeout,
        )

        self._client.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": (
                    f"Bearer {self.settings.mcp_github_pat.get_secret_value()}"
                ),
                "X-GitHub-Api-Version": settings.github_api_version,
            }
        )

        self._repo_path = (
            f"/repos/{settings.repository_owner}/"
            f"{settings.repository_name}"
        )

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> Any:
        try:
            response = await self._client.request(
                method,
                endpoint,
                **kwargs,
            )

        except httpx.TimeoutException as exc:
            raise GitHubConnectionError(
                "GitHub API request timed out"
            ) from exc

        except httpx.RequestError as exc:
            raise GitHubConnectionError(
                f"GitHub API connection failed: {exc}"
            ) from exc

        if response.is_success:
            if response.status_code == 204 or not response.content:
                return None

            return response.json()

        try:
            body = response.json()
            message = body.get("message", response.text)
        except ValueError:
            body = {}
            message = response.text

        error_class = GitHubAPIError

        if response.status_code == 404:
            error_class = GitHubNotFoundError

        elif response.status_code in (401, 403):
            error_class = GitHubAuthenticationError

        raise error_class(
            status_code=response.status_code,
            message=message,
            response_body=response.text,
        )

    async def _get_paginated(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1

        while True:
            page_params = {
                **(params or {}),
                "per_page": 100,
                "page": page,
            }

            data = await self._request(
                "GET",
                endpoint,
                params=page_params,
            )

            if not isinstance(data, list):
                raise GitHubAPIError(
                    status_code=502,
                    message="Expected a list from GitHub API",
                )

            results.extend(data)

            if len(data) < 100:
                break

            page += 1

        return results

    async def list_issues(
        self,
        state: str = "all",
        labels: list[str] | None = None,
    ) -> list[GitHubIssue]:
        params: dict[str, Any] = {
            "state": state,
            "sort": "updated",
            "direction": "asc",
        }

        if labels:
            params["labels"] = ",".join(labels)

        data = await self._get_paginated(
            f"{self._repo_path}/issues",
            params=params,
        )

        return [
            GitHubIssue.model_validate(issue)
            for issue in data
            if "pull_request" not in issue
        ]

    async def get_issue(
        self,
        issue_number: int,
    ) -> GitHubIssue:
        self._validate_issue_number(issue_number)

        data = await self._request(
            "GET",
            f"{self._repo_path}/issues/{issue_number}",
        )

        return GitHubIssue.model_validate(data)

    async def get_issue_comments(
        self,
        issue_number: int,
    ) -> list[GitHubComment]:
        self._validate_issue_number(issue_number)

        data = await self._get_paginated(
            f"{self._repo_path}/issues/{issue_number}/comments",
        )

        return [
            GitHubComment.model_validate(comment)
            for comment in data
        ]

    async def create_issue_comment(
        self,
        issue_number: int,
        body: str,
    ) -> GitHubComment:
        self._validate_issue_number(issue_number)

        data = await self._request(
            "POST",
            f"{self._repo_path}/issues/{issue_number}/comments",
            json={"body": body},
        )

        return GitHubComment.model_validate(data)

    async def close_issue(
        self,
        issue_number: int,
    ) -> GitHubIssue:
        self._validate_issue_number(issue_number)

        data = await self._request(
            "PATCH",
            f"{self._repo_path}/issues/{issue_number}",
            json={"state": "closed"},
        )

        return GitHubIssue.model_validate(data)

    @staticmethod
    def _validate_issue_number(issue_number: int) -> None:
        if issue_number <= 0:
            raise ValueError(
                "Issue number must be a positive integer"
            )

    async def list_labels(self) -> list[GitHubLabel]:
        """Retrieve all labels from the configured repository."""

        data = await self._get_paginated(
            f"{self._repo_path}/labels",
        )

        return [
            GitHubLabel.model_validate(label)
            for label in data
        ]

    async def create_label(
        self,
        name: str,
        color: str,
        description: str = "",
    ) -> GitHubLabel:
        """Create a label in the configured repository."""

        name = name.strip()
        color = color.strip().lstrip("#")

        if not name:
            raise ValueError("Label name cannot be empty.")

        if len(color) != 6 or any(
            char not in "0123456789abcdefABCDEF"
            for char in color
        ):
            raise ValueError(
                "Label color must be a 6-character hex value."
            )

        data = await self._request(
            "POST",
            f"{self._repo_path}/labels",
            json={
                "name": name,
                "color": color,
                "description": description,
            },
        )

        return GitHubLabel.model_validate(data)

    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> GitHubIssue:
        """Create an issue in the configured repository."""

        title = title.strip()

        if not title:
            raise ValueError("Issue title cannot be empty.")

        data = await self._request(
            "POST",
            f"{self._repo_path}/issues",
            json={
                "title": title,
                "body": body,
                "labels": labels or [],
            },
        )

        return GitHubIssue.model_validate(data)

    