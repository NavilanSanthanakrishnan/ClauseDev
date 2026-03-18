import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_LOADED = False

def _resolve_env_file() -> Path:
    app_env = os.getenv("APP_ENV", "local").strip().lower()
    repo_root = Path(__file__).resolve().parents[3]
    if app_env == "production":
        return repo_root / ".env.production"
    return repo_root / ".env.local"


def load_app_env() -> Path:
    global _ENV_LOADED
    env_file = _resolve_env_file()
    if not _ENV_LOADED:
        if env_file.exists():
            load_dotenv(env_file, override=False)
        _ENV_LOADED = True
    return env_file