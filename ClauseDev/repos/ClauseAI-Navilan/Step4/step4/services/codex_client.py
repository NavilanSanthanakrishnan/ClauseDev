from __future__ import annotations

import json
import re
from typing import Any, Iterable

import httpx

from step4.config import get_settings
from step4.services.codex_auth import CodexAuthError, resolve_codex_runtime_credentials


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
            data = "\n".join(data_lines).strip()
            if not data or data == "[DONE]":
                continue
            try:
                yield json.loads(data)
            except Exception:
                continue
            continue
        buffer.append(line)


def _consume_codex_sse(response: httpx.Response) -> str:
    content = ""
    for event in _iter_sse(response):
        event_type = event.get("type")
        if event_type == "response.output_text.delta":
            content += event.get("delta") or ""
        elif event_type in {"error", "response.failed"}:
            raise RuntimeError("Codex response failed.")
    return content


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("Empty LLM response.")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in response.")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object.")
    return parsed


class CodexClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def chat(self, *, system_prompt: str, user_prompt: str, model: str | None = None) -> str:
        model = model or self.settings.codex_model
        creds = resolve_codex_runtime_credentials(
            codex_home=self.settings.codex_home,
            refresh_if_expiring=True,
            refresh_timeout_seconds=self.settings.codex_refresh_timeout_seconds,
        )

        body: dict[str, Any] = {
            "model": model,
            "store": False,
            "stream": True,
            "instructions": system_prompt,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                }
            ],
            "text": {"verbosity": self.settings.codex_verbosity},
        }
        headers = {
            "Authorization": f"Bearer {creds['access_token']}",
            "chatgpt-account-id": creds["account_id"],
            "OpenAI-Beta": "responses=experimental",
            "originator": self.settings.codex_originator,
            "User-Agent": "Step4/1.0 (python)",
            "accept": "text/event-stream",
            "content-type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                with client.stream("POST", f"{self.settings.codex_base_url}/responses", headers=headers, json=body) as response:
                    if response.status_code != 200:
                        raw = response.read().decode("utf-8", "ignore")
                        raise RuntimeError(f"Codex request failed with status {response.status_code}: {raw}")
                    return _consume_codex_sse(response).strip()
        except CodexAuthError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Codex request failed: {exc}") from exc

    def chat_json(self, *, system_prompt: str, user_prompt: str, model: str | None = None) -> dict[str, Any]:
        return extract_json_from_text(self.chat(system_prompt=system_prompt, user_prompt=user_prompt, model=model))
