from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    otari_base_url: str
    otari_api_key: str
    otari_mcp_server_id: str

    tr_planner_model: str
    tr_compiler_model: str

    tr_admin_token: str
    tr_db_path: str = "./data/trustrail.db"

    mcp_github_pat: str
    mcp_admin_token: str

    fake_otari: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()