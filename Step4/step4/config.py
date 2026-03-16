from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


APP_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(APP_ROOT / ".env")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Step4 Conflict Finder")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = _int_env("APP_PORT", 8012)
    app_reload: bool = _bool_env("APP_RELOAD", False)
    debug: bool = _bool_env("DEBUG", False)

    california_postgres_host: str = os.getenv("CALIFORNIA_POSTGRES_HOST", "127.0.0.1")
    california_postgres_port: int = _int_env("CALIFORNIA_POSTGRES_PORT", 55432)
    california_postgres_db: str = os.getenv("CALIFORNIA_POSTGRES_DB", "california_code")
    california_postgres_user: str = os.getenv("CALIFORNIA_POSTGRES_USER", "navilan")
    california_postgres_password: str = os.getenv("CALIFORNIA_POSTGRES_PASSWORD", "")

    uscode_postgres_host: str = os.getenv("USCODE_POSTGRES_HOST", "127.0.0.1")
    uscode_postgres_port: int = _int_env("USCODE_POSTGRES_PORT", 55432)
    uscode_postgres_db: str = os.getenv("USCODE_POSTGRES_DB", "uscode_local")
    uscode_postgres_user: str = os.getenv("USCODE_POSTGRES_USER", "navilan")
    uscode_postgres_password: str = os.getenv("USCODE_POSTGRES_PASSWORD", "")

    postgres_min_pool_size: int = _int_env("POSTGRES_MIN_POOL_SIZE", 1)
    postgres_max_pool_size: int = _int_env("POSTGRES_MAX_POOL_SIZE", 4)

    codex_home: str = os.getenv("CODEX_HOME", str(Path.home() / ".codex"))
    codex_base_url: str = os.getenv("CODEX_BASE_URL", "https://chatgpt.com/backend-api/codex")
    codex_model: str = os.getenv("CODEX_MODEL", "gpt-5.4")
    codex_originator: str = os.getenv("CODEX_ORIGINATOR", "step4-conflict-finder")
    codex_verbosity: str = os.getenv("CODEX_VERBOSITY", "medium")
    llm_timeout_seconds: float = _float_env("LLM_TIMEOUT_SECONDS", 150.0)
    llm_max_output_tokens: int = _int_env("LLM_MAX_OUTPUT_TOKENS", 6000)
    codex_refresh_timeout_seconds: float = _float_env("CODEX_REFRESH_TIMEOUT_SECONDS", 20.0)

    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", APP_ROOT / "uploads")).expanduser()
    max_upload_bytes: int = _int_env("MAX_UPLOAD_BYTES", 20 * 1024 * 1024)
    max_bill_chars_for_llm: int = _int_env("MAX_BILL_CHARS_FOR_LLM", 50000)

    california_lexical_limit: int = _int_env("CALIFORNIA_LEXICAL_LIMIT", 80)
    uscode_lexical_limit: int = _int_env("USCODE_LEXICAL_LIMIT", 80)
    semantic_input_limit: int = _int_env("SEMANTIC_INPUT_LIMIT", 24)
    llm_input_limit: int = _int_env("LLM_INPUT_LIMIT", 12)
    final_result_limit: int = _int_env("FINAL_RESULT_LIMIT", 10)
    excerpt_char_limit: int = _int_env("EXCERPT_CHAR_LIMIT", 1000)

    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "cpu")
    embedding_batch_size: int = _int_env("EMBEDDING_BATCH_SIZE", 16)

    require_bootstrap_indexes: bool = _bool_env("REQUIRE_BOOTSTRAP_INDEXES", True)

    @property
    def california_dsn(self) -> str:
        return _dsn(
            host=self.california_postgres_host,
            port=self.california_postgres_port,
            db=self.california_postgres_db,
            user=self.california_postgres_user,
            password=self.california_postgres_password,
        )

    @property
    def uscode_dsn(self) -> str:
        return _dsn(
            host=self.uscode_postgres_host,
            port=self.uscode_postgres_port,
            db=self.uscode_postgres_db,
            user=self.uscode_postgres_user,
            password=self.uscode_postgres_password,
        )


def _dsn(*, host: str, port: int, db: str, user: str, password: str) -> str:
    parts = [
        f"host={host}",
        f"port={port}",
        f"dbname={db}",
        f"user={user}",
    ]
    if password:
        parts.append(f"password={password}")
    return " ".join(parts)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
