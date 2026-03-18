from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

import httpx

from clauseai_backend.core.config import settings
from clauseai_backend.services.codex_auth import resolve_codex_runtime_credentials


def _responses_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/responses"):
        return normalized
    return f"{normalized}/responses"


def _iter_sse(response: httpx.Response) -> Iterable[dict[str, Any]]:
    buffer: list[str] = []
    for line in response.iter_lines():
        if line == "":
            if not buffer:
                continue
            data_lines = [entry[5:].strip() for entry in buffer if entry.startswith("data:")]
            buffer = []
            if not data_lines:
                continue
            payload = "\n".join(data_lines).strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                yield json.loads(payload)
            except Exception:
                continue
            continue
        buffer.append(line)


def _consume_codex_sse(response: httpx.Response) -> str:
    content = ""
    for event in _iter_sse(response):
        event_type = event.get("type")
        if event_type == "response.output_text.delta":
            content += str(event.get("delta") or "")
        elif event_type in {"error", "response.failed"}:
            raise RuntimeError(f"Codex response failed: {event}")
    return content.strip()


def extract_json_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty model response.")
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in model response.")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Model response is not a JSON object.")
    return parsed


class CodexClient:
    def chat(self, *, system_prompt: str, user_prompt: str, model: str | None = None) -> str:
        creds = resolve_codex_runtime_credentials()
        body: dict[str, Any] = {
            "model": model or settings.codex_model,
            "store": False,
            "stream": True,
            "instructions": system_prompt,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                }
            ],
            "text": {"verbosity": settings.codex_verbosity},
            "reasoning": {"effort": settings.codex_reasoning_effort},
        }
        headers = {
            "Authorization": f"Bearer {creds['access_token']}",
            "chatgpt-account-id": creds["account_id"],
            "OpenAI-Beta": "responses=experimental",
            "originator": settings.codex_originator,
            "User-Agent": "ClauseAIProd/1.0 (python)",
            "accept": "text/event-stream",
            "content-type": "application/json",
        }
        with httpx.Client(timeout=settings.codex_timeout_seconds) as client:
            with client.stream("POST", _responses_url(settings.codex_base_url), headers=headers, json=body) as response:
                if response.status_code != 200:
                    raw = response.read().decode("utf-8", "ignore")
                    raise RuntimeError(f"Codex request failed with status {response.status_code}: {raw}")
                return _consume_codex_sse(response)

    def chat_json(self, *, system_prompt: str, user_prompt: str, model: str | None = None) -> dict[str, Any]:
        return extract_json_from_text(self.chat(system_prompt=system_prompt, user_prompt=user_prompt, model=model))
