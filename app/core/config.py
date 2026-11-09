
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Otari configuration
    otari_base_url: str
    otari_api_key: str
    # otari_mcp_server_id: str
    otari_timeout: float = 60.0
    otari_mcp_server_id: str | None = None

    # # AI model configuration
    tr_planner_model: str
    tr_compiler_model: str
    tr_agent_max_iterations: int = 8
    tr_agent_max_tool_calls: int = 16
    tr_agent_max_completion_tokens: int = 512
    tr_agent_token_budget: int = 4096
    # tr_compiler_model: str

    # # TrustRail configuration
    # tr_admin_token: str
    tr_db_path: str = "./data/trustrail.db"

    # # GitHub MCP configuration
    # GitHub MCP configuration
    mcp_github_pat: str
    mcp_github_repo: str
    mcp_admin_token: str
    otari_agent_api_key: str  # Dedicated agent-run key
    

    # # Development configuration
    # fake_otari: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()  # type: ignore[call-arg]
