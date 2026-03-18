from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from clauseai_backend.api.deps import get_current_user
from clauseai_backend.core.config import settings as app_settings
from clauseai_backend.models.auth import User

router = APIRouter(prefix="/api/settings", tags=["settings"])

_SETTINGS_PATH: Path = app_settings.storage_root.parent / "openai_settings.json"


def _read() -> dict:
    if not _SETTINGS_PATH.is_file():
        return {}
    try:
        return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(data: dict) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


class OpenAISettingsResponse(BaseModel):
    base_url: str
    api_key_set: bool
    model: str
    enabled: bool


class OpenAISettingsUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None


@router.get("/openai", response_model=OpenAISettingsResponse)
def get_openai_settings(_: User = Depends(get_current_user)) -> OpenAISettingsResponse:
    data = _read()
    return OpenAISettingsResponse(
        base_url=str(data.get("base_url") or ""),
        api_key_set=bool(data.get("api_key")),
        model=str(data.get("model") or ""),
        enabled=bool(data.get("base_url") and data.get("api_key") and data.get("model")),
    )


@router.put("/openai", response_model=OpenAISettingsResponse)
def update_openai_settings(
    payload: OpenAISettingsUpdate,
    _: User = Depends(get_current_user),
) -> OpenAISettingsResponse:
    current = _read()
    if payload.base_url is not None:
        current["base_url"] = payload.base_url
    if payload.api_key is not None:
        current["api_key"] = payload.api_key
    if payload.model is not None:
        current["model"] = payload.model
    _write(current)
    return get_openai_settings(_)


@router.delete("/openai")
def clear_openai_settings(_: User = Depends(get_current_user)) -> dict[str, bool]:
    if _SETTINGS_PATH.is_file():
        _SETTINGS_PATH.unlink()
    return {"success": True}
