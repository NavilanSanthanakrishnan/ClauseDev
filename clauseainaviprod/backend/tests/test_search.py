from __future__ import annotations

from fastapi.testclient import TestClient

from clause_backend.main import create_app
from clause_backend.schemas import SearchFilters
from clause_backend.services.agentic_search import agentic_search
from clause_backend.services.standard_search import infer_filters, search_bills


def test_standard_search_infers_jurisdiction_without_hardcoded_topic_expansion(test_database: None) -> None:
    response = search_bills("fluoride water in Tennessee", SearchFilters(limit=3))

    assert response.plan["effective_filters"]["jurisdiction"] == "Tennessee"
    assert response.items
    assert response.items[0].bill_id == "tn-fluoride-1"


def test_standard_search_prefers_longer_jurisdiction_match() -> None:
    response = infer_filters("department health rules in West Virginia", SearchFilters(limit=5))

    assert response.jurisdiction == "West Virginia"


def test_standard_search_recent_sort_prefers_newer_match(test_database: None) -> None:
    response = search_bills("data broker privacy", SearchFilters(limit=2, sort="recent"))

    assert [item.bill_id for item in response.items[:2]] == ["wa-privacy-new", "tn-privacy-old"]
    assert response.plan["effective_filters"]["topic"] is None


def test_standard_search_exact_identifier_beats_generic_prefix_matches(test_database: None) -> None:
    response = search_bills("HB 2200", SearchFilters(limit=3))

    assert response.items
    assert response.items[0].bill_id == "wa-privacy-new"
    assert response.plan["identifier_query"] is True


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


def test_bill_detail_route_accepts_slashes_in_bill_ids(monkeypatch) -> None:
    monkeypatch.setattr(
        "clause_backend.api.get_bill",
        lambda bill_id: {
            "bill_id": bill_id,
            "identifier": "HB 1",
            "jurisdiction": "Test",
            "state_code": "TS",
            "title": "Test Bill",
            "summary": "Summary",
            "status": "Filed",
            "outcome": "Active",
            "sponsor": "Rep. Test",
            "committee": "Committee",
            "session_name": "2026",
            "source_url": None,
            "topics": ["test"],
            "full_text": "Full text",
            "latest_action_date": None,
        },
    )

    with TestClient(create_app()) as client:
        detail = client.get("/api/bills/ocd-bill%2Fabc123")

    assert detail.status_code == 200
    assert detail.json()["bill_id"] == "ocd-bill/abc123"


def test_standard_search_handles_hyphenated_identifier_query(test_database: None) -> None:
    response = search_bills("HB-2200", SearchFilters(limit=3))

    assert response.items
    assert response.items[0].bill_id == "wa-privacy-new"
