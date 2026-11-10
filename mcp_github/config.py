
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    mcp_github_pat: SecretStr
    mcp_github_repo: str
    trustrail_admin_token: SecretStr

    github_api_url: str = "https://api.github.com"
    github_api_version: str = "2022-11-28"
    github_timeout: float = 20.0

    demo_ages_file: Path = Path("demo-ages.json")

    # Explicitly disabled unless enabled in the demo MCP server environment.
    trustrail_enable_naive_demo: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("mcp_github_repo")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        value = value.strip()
        parts = value.split("/")

        if len(parts) != 2 or not all(parts):
            raise ValueError(
                "Repository must be in owner/repository format"
            )

        return value

    @property
    def repository_owner(self) -> str:
        return self.mcp_github_repo.split("/")[0]

    @property
    def repository_name(self) -> str:
        return self.mcp_github_repo.split("/")[1]
