from collections.abc import Sequence
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="CLAUSEAI_",
        case_sensitive=False,
    )

    app_name: str = "ClauseAIProd"
    app_env: str = "local"
    debug: bool = True
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )
    user_database_url: str = "postgresql+psycopg:///clauseai-db-user"
    reference_database_url: str = "postgresql+psycopg:///clauseai-db"
    openstates_database_url: str = "postgresql+psycopg:///openstates"
    california_code_database_url: str = "postgresql+psycopg:///california_code"
    legal_index_database_url: str = "postgresql+psycopg:///clause_legal_index"
    uscode_database_url: str = "postgresql+psycopg:///uscode_local"
    jwt_secret: str = "change-me-in-env-change-me-in-env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    storage_root: Path = Path("data/storage")
    codex_home: Path = Path.home() / ".codex"
    codex_base_url: str = "https://chatgpt.com/backend-api/codex"
    codex_model: str = "gpt-5.4-mini"
    codex_originator: str = "clauseai-prod"
    codex_verbosity: str = "medium"
    codex_timeout_seconds: float = 120.0
    codex_refresh_timeout_seconds: float = 20.0
    codex_reasoning_effort: str = "low"
    codex_app_server_host: str = "127.0.0.1"
    codex_app_server_port: int = 8766
    max_draft_chars_for_model: int = 50000
    max_reference_items_for_model: int = 8

    @property
    def allowed_cors_origins(self) -> Sequence[str]:
        return [origin.strip() for origin in self.cors_origins if origin.strip()]

    @property
    def codex_app_server_ws_url(self) -> str:
        return f"ws://{self.codex_app_server_host}:{self.codex_app_server_port}"

    @property
    def codex_app_server_health_url(self) -> str:
        return f"http://{self.codex_app_server_host}:{self.codex_app_server_port}/readyz"


settings = Settings()
