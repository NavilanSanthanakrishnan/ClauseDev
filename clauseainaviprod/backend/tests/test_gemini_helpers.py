from __future__ import annotations

import httpx

from clause_backend.services import gemini


def test_rerank_candidates_accepts_list_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        gemini,
        "generate_json",
        lambda prompt: [{"id": "a", "score": 91, "reason": "Direct match"}],
    )

    response = gemini.rerank_candidates("query", "intent", [{"id": "a", "title": "Title"}])

    assert response == {"a": {"score": 91.0, "reason": "Direct match"}}


def test_generate_json_falls_back_on_http_errors(monkeypatch) -> None:
    monkeypatch.setattr(gemini.settings, "gemini_api_key", "test-key")

    def raise_rate_limit(*_args, **_kwargs):
        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(gemini, "_post_with_retry", raise_rate_limit)

    assert gemini.generate_json("plan this search") is None
