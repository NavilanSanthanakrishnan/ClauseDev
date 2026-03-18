from __future__ import annotations

from clause_backend.services import gemini


def test_rerank_candidates_accepts_list_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        gemini,
        "generate_json",
        lambda prompt: [{"id": "a", "score": 91, "reason": "Direct match"}],
    )

    response = gemini.rerank_candidates("query", "intent", [{"id": "a", "title": "Title"}])

    assert response == {"a": {"score": 91.0, "reason": "Direct match"}}
