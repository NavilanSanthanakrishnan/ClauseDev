from __future__ import annotations

from fastapi.testclient import TestClient

from clause_backend.main import create_app
from clause_backend.schemas import LawSearchFilters
from clause_backend.services.agentic_law_search import agentic_law_search
from clause_backend.services.law_search import search_laws


CA_PRIVACY_LAW = {
    "document_id": "ca_code:ca-1",
    "citation": "CIV 1798.99.31",
    "jurisdiction": "California",
    "source": "California Code",
    "heading": "Consumer Data Broker Duties",
    "hierarchy_path": "Division 3 > Part 4",
    "body_excerpt": "A data broker shall honor consumer deletion requests and maintain a privacy contact method.",
    "source_url": "https://example.com/ca-privacy",
    "lexical_rank": 0.82,
}

US_WILDFIRE_LAW = {
    "document_id": "uscode:usc-1",
    "citation": "16 U.S.C. § 2101",
    "jurisdiction": "United States",
    "source": "United States Code",
    "heading": "Wildfire risk reduction assistance",
    "hierarchy_path": "Title 16 > Chapter 41",
    "body_excerpt": "The Secretary may support wildfire risk reduction and hazardous fuels projects.",
    "source_url": "https://example.com/us-wildfire",
    "lexical_rank": 0.76,
}


def test_standard_law_search_infers_california_jurisdiction(monkeypatch) -> None:
    monkeypatch.setattr("clause_backend.repositories.laws.search_california_laws", lambda query, limit: [CA_PRIVACY_LAW])
    monkeypatch.setattr("clause_backend.repositories.laws.search_uscode_laws", lambda query, limit: [US_WILDFIRE_LAW])

    response = search_laws("california data broker privacy", LawSearchFilters(limit=5))

    assert response.plan["effective_filters"]["jurisdiction"] == "California"
    assert response.items[0].document_id == "ca_code:ca-1"
    assert response.items[0].source == "California Code"


def test_agentic_law_search_returns_conflict_candidate(monkeypatch) -> None:
    monkeypatch.setattr("clause_backend.repositories.laws.search_california_laws", lambda query, limit: [CA_PRIVACY_LAW])
    monkeypatch.setattr("clause_backend.repositories.laws.search_uscode_laws", lambda query, limit: [])

    response = agentic_law_search("Which law contradicts this section about data broker deletion rights", LawSearchFilters(limit=5))

    assert response.items
    assert response.items[0].document_id == "ca_code:ca-1"
    assert response.mode == "agentic"


def test_agentic_law_search_sanitizes_gemini_filters(monkeypatch) -> None:
    monkeypatch.setattr(
        "clause_backend.services.agentic_law_search.gemini_plan",
        lambda query, filters: {
            "intent": "labor retaliation laws",
            "rewrites": ["labor retaliation laws"],
            "filters": {"jurisdiction": "California", "source": "statutes"},
            "used_gemini": True,
        },
    )
    monkeypatch.setattr("clause_backend.repositories.laws.search_california_laws", lambda query, limit: [CA_PRIVACY_LAW])
    monkeypatch.setattr("clause_backend.repositories.laws.search_uscode_laws", lambda query, limit: [US_WILDFIRE_LAW])

    response = agentic_law_search("Find California laws about labor retaliation", LawSearchFilters(limit=5))

    assert response.plan["effective_filters"]["jurisdiction"] == "California"
    assert response.plan["effective_filters"]["source"] is None


def test_law_api_returns_stats_and_detail(monkeypatch) -> None:
    monkeypatch.setattr(
        "clause_backend.api.law_stats",
        lambda: {
            "total_laws": 2,
            "california_laws": 1,
            "federal_laws": 1,
        },
    )
    monkeypatch.setattr(
        "clause_backend.api.get_law_detail",
        lambda document_id: {
            "document_id": document_id,
            "citation": "CIV 1798.99.31",
            "jurisdiction": "California",
            "source": "California Code",
            "heading": "Consumer Data Broker Duties",
            "hierarchy_path": "Division 3 > Part 4",
            "body_excerpt": "excerpt",
            "source_url": "https://example.com/ca-privacy",
            "matched_reasons": [],
            "relevance_score": 0.0,
            "body_text": "full body",
        },
    )

    with TestClient(create_app()) as client:
        stats = client.get("/api/laws/stats")
        detail = client.get("/api/laws/ca_code:ca-1")

    assert stats.status_code == 200
    assert stats.json()["total_laws"] == 2
    assert detail.status_code == 200
    assert detail.json()["citation"] == "CIV 1798.99.31"


def test_law_detail_route_accepts_slashes_in_document_ids(monkeypatch) -> None:
    monkeypatch.setattr(
        "clause_backend.api.get_law_detail",
        lambda document_id: {
            "document_id": document_id,
            "citation": "16 U.S.C. § 6592",
            "jurisdiction": "United States",
            "source": "United States Code",
            "heading": "Wildfire law",
            "hierarchy_path": "Title 16",
            "body_excerpt": "excerpt",
            "source_url": "https://example.com/uscode",
            "matched_reasons": [],
            "relevance_score": 0.0,
            "body_text": "full body",
        },
    )

    with TestClient(create_app()) as client:
        detail = client.get("/api/laws/uscode%3A/us/usc/t16/s6592")

    assert detail.status_code == 200
    assert detail.json()["document_id"] == "uscode:/us/usc/t16/s6592"
