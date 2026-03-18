from __future__ import annotations

import json
from typing import Any

import httpx

from clause_backend.core.config import settings


class GeminiUnavailableError(RuntimeError):
    pass


def gemini_available() -> bool:
    return bool(settings.gemini_api_key)


def _endpoint(model: str, action: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{action}"


def generate_json(prompt: str) -> dict[str, Any] | None:
    if not gemini_available():
        return None

    response = httpx.post(
        _endpoint(settings.gemini_model, "generateContent"),
        params={"key": settings.gemini_api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        },
        timeout=settings.gemini_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    parts = payload["candidates"][0]["content"]["parts"]
    text = "".join(part.get("text", "") for part in parts)
    if not text.strip():
        return None
    return json.loads(text)


def embed_text(text: str) -> list[float] | None:
    if not gemini_available():
        return None

    response = httpx.post(
        _endpoint(settings.gemini_embedding_model, "embedContent"),
        params={"key": settings.gemini_api_key},
        json={
            "model": f"models/{settings.gemini_embedding_model}",
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_QUERY",
        },
        timeout=settings.gemini_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("embedding", {}).get("values")

