from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from clauseai_backend.core.config import settings as app_settings
from clauseai_backend.services.codex_client import extract_json_from_text

_SETTINGS_PATH: Path = app_settings.storage_root.parent / "openai_settings.json"


def _load_settings() -> dict[str, str] | None:
    """Read saved OpenAI-compatible endpoint config, return None if not configured."""
    if not _SETTINGS_PATH.is_file():
        return None
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        if data.get("base_url") and data.get("api_key") and data.get("model"):
            return {k: str(v) for k, v in data.items()}
    except Exception:
        pass
    return None


def openai_compat_available() -> bool:
    """Return True when a valid OpenAI-compatible endpoint is configured."""
    return _load_settings() is not None


def openai_compat_chat_json(*, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
    """
    POST to /chat/completions on the configured OpenAI-compatible endpoint.
    Parses the assistant message content as JSON and returns it, or None on any error.
    """
    cfg = _load_settings()
    if cfg is None:
        return None
    base_url = cfg["base_url"].rstrip("/")
    try:
        with httpx.Client(timeout=app_settings.codex_timeout_seconds) as client:
            resp = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return extract_json_from_text(content)
    except Exception:
        return None
