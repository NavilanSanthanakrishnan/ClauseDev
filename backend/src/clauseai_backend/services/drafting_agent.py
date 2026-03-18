from __future__ import annotations

import json
from typing import Any

from clauseai_backend.core.config import settings
from clauseai_backend.services.codex_auth import CodexAuthError, codex_auth_available
from clauseai_backend.services.openai_compat_client import openai_compat_available, openai_compat_chat_json
from clauseai_backend.services.codex_client import CodexClient
from clauseai_backend.services.prompt_loader import load_prompt


def build_editor_agent_pass(
    *,
    draft_text: str,
    project_title: str,
    metadata: dict[str, Any],
    suggestions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    payload = {
        "project_title": project_title,
        "metadata": metadata,
        "draft_text": draft_text[: settings.max_draft_chars_for_model],
        "suggestions": suggestions[:20],
    }
    sys_prompt = load_prompt("editor_agent_system_prompt.txt")
    usr_prompt = json.dumps(payload, indent=2)
    if openai_compat_available():
        result = openai_compat_chat_json(system_prompt=sys_prompt, user_prompt=usr_prompt)
        if result is not None:
            return result
    if not codex_auth_available():
        return None
    try:
        return CodexClient().chat_json(system_prompt=sys_prompt, user_prompt=usr_prompt)
    except (RuntimeError, ValueError, CodexAuthError):
        return None
