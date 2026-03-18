from __future__ import annotations

import json
import time
from typing import Any

import httpx

from clause_backend.core.config import settings


class GeminiUnavailableError(RuntimeError):
    pass


def gemini_available() -> bool:
    return bool(settings.gemini_api_key)


def _endpoint(model: str, action: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{action}"


def _post_with_retry(model: str, action: str, payload: dict[str, Any]) -> httpx.Response:
    last_error: httpx.HTTPStatusError | None = None
    for attempt in range(5):
        response = httpx.post(
            _endpoint(model, action),
            params={"key": settings.gemini_api_key},
            json=payload,
            timeout=settings.gemini_timeout_seconds,
        )
        try:
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as error:
            last_error = error
            if response.status_code != 429 or attempt == 4:
                raise
            retry_after = response.headers.get("retry-after")
            delay = float(retry_after) if retry_after else min(30.0, 2 ** attempt)
            time.sleep(delay)
    if last_error:
        raise last_error
    raise RuntimeError("Gemini request failed without an HTTP response.")


def generate_json(prompt: str) -> dict[str, Any] | None:
    if not gemini_available():
        return None

    try:
        response = _post_with_retry(
            settings.gemini_model,
            "generateContent",
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
        )
        payload = response.json()
        parts = payload["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError):
        return None

    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def embed_text(text: str) -> list[float] | None:
    if not gemini_available():
        return None

    try:
        response = _post_with_retry(
            settings.gemini_embedding_model,
            "embedContent",
            {
                "model": f"models/{settings.gemini_embedding_model}",
                "content": {"parts": [{"text": text}]},
                "taskType": "RETRIEVAL_QUERY",
            },
        )
        payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return None
    return payload.get("embedding", {}).get("values")


def rerank_candidates(query: str, intent: str, candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]] | None:
    if not candidates:
        return {}

    payload = generate_json(
        json.dumps(
            {
                "task": "Rerank legislative search candidates against the user's request.",
                "instructions": [
                    "Return JSON only.",
                    "Score each candidate from 0 to 100.",
                    "Prefer candidates that directly satisfy the query and intent.",
                    "Do not reward generic same-jurisdiction matches if the policy terms do not align.",
                    "Keep each reason short and evidence-based.",
                ],
                "query": query,
                "intent": intent,
                "candidates": candidates,
                "response_schema": {
                    "items": [{"id": "candidate id", "score": "0-100 integer", "reason": "short explanation"}]
                },
            }
        )
    )
    if not payload:
        return None
    if isinstance(payload, list):
        items = payload
    else:
        items = payload.get("items")
    if not isinstance(items, list):
        return None

    ranked: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate_id = item.get("id")
        if not isinstance(candidate_id, str):
            continue
        score = item.get("score")
        reason = item.get("reason")
        ranked[candidate_id] = {
            "score": float(score) if isinstance(score, (int, float)) else 0.0,
            "reason": str(reason).strip() if reason else "Gemini rerank",
        }
    return ranked
