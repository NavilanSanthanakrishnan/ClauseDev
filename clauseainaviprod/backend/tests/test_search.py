from __future__ import annotations

from fastapi.testclient import TestClient

from clause_backend.main import create_app
from clause_backend.schemas import SearchFilters
from clause_backend.services.agentic_search import agentic_search
from clause_backend.services.standard_search import search_bills


def test_standard_search_infers_filters_for_jurisdiction_and_topic(test_database: None) -> None:
    response = search_bills("fluoride water in Tennessee", SearchFilters(limit=3))

    assert response.plan["effective_filters"]["jurisdiction"] == "Tennessee"
    assert response.items
    assert response.items[0].bill_id == "tn-fluoride-1"
    assert any("Jurisdiction matched Tennessee" in reason for reason in response.items[0].matched_reasons)


def test_standard_search_recent_sort_prefers_newer_match(test_database: None) -> None:
    response = search_bills("data broker privacy", SearchFilters(limit=2, sort="recent"))

    assert [item.bill_id for item in response.items[:2]] == ["wa-privacy-new", "tn-privacy-old"]
    assert response.plan["effective_filters"]["topic"] == "privacy"


def test_agentic_search_broadens_scope_when_state_has_no_hits(test_database: None) -> None:
    response = agentic_search("Find me similar education appointment bills in Hawaii", SearchFilters(limit=3))

    assert response.plan["effective_filters"]["jurisdiction"] == "Hawaii"
    assert response.plan["broadened_scope"] is True
    assert response.items
    assert response.items[0].bill_id == "in-education-1"


def test_api_serves_stats_and_bill_detail(test_database: None) -> None:
    with TestClient(create_app()) as client:
        stats = client.get("/api/stats")
        detail = client.get("/api/bills/in-education-1")

    assert stats.status_code == 200
    assert stats.json()["total_bills"] == 4
    assert detail.status_code == 200
    assert detail.json()["identifier"] == "HB 1004"
