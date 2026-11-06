
class GitHubError(Exception):
    """Base exception for GitHub integration errors."""


class GitHubAPIError(GitHubError):
    """GitHub returned an unsuccessful HTTP response."""

    def __init__(
        self,
        status_code: int,
        message: str,
        response_body: str = "",
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.response_body = response_body

        super().__init__(
            f"GitHub API error ({status_code}): {message}"
        )


class GitHubConnectionError(GitHubError):
    """Unable to communicate with GitHub."""


class GitHubNotFoundError(GitHubAPIError):
    """Requested GitHub resource does not exist."""


class GitHubAuthenticationError(GitHubAPIError):
    """GitHub authentication or authorization failed."""
