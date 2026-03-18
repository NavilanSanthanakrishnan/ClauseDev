from __future__ import annotations

from fastapi.testclient import TestClient

from clause_backend.core.config import settings
from clause_backend.main import create_app


def login_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": settings.auth_dummy_email, "password": settings.auth_dummy_password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_auth_enabled_requires_login(test_database: None, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    with TestClient(create_app()) as client:
        unauthorized = client.get("/api/stats")
        headers = login_headers(client)
        authorized = client.get("/api/stats", headers=headers)

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["total_bills"] == 4


def test_project_crud_refresh_and_agent(test_database: None, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(
        "clause_backend.api.refresh_project_insights",
        lambda project: {
            "similar_bills": {"items": [{"bill_id": "wa-privacy-new", "identifier": "HB 2200", "title": "Consumer Data Broker Accountability Act"}]},
            "conflicting_laws": {"items": [{"document_id": "ca_code:ca-1", "citation": "CIV 1798.99.31", "heading": "Consumer Data Broker Duties"}]},
            "stakeholders": {"supporters": ["Privacy coalition"], "opponents": ["Industry trade group"]},
            "drafting_focus": {"next_actions": ["Narrow enforcement scope"]},
        },
    )
    monkeypatch.setattr(
        "clause_backend.api.agent_chat",
        lambda project, user_message: {
            "message": {
                "message_id": "msg-test",
                "role": "assistant",
                "content": f"Agent reviewed: {user_message}",
                "tool_trace": [],
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            "tool_trace": [],
            "suggested_stage": "Review",
            "suggested_status": "Needs revision",
            "revision_excerpt": "Section 1. Narrow the definition.",
        },
    )

    with TestClient(create_app()) as client:
        headers = login_headers(client)

        projects = client.get("/api/projects", headers=headers)
        assert projects.status_code == 200
        assert len(projects.json()) >= 2

        created = client.post(
            "/api/projects",
            headers=headers,
            json={
                "title": "Water safety phase-in act",
                "policy_goal": "Require water quality disclosures with a phased implementation window.",
                "jurisdiction": "Tennessee",
            },
        )
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        updated = client.put(
            f"/api/projects/{project_id}",
            headers=headers,
            json={
                "status": "In drafting",
                "stage": "Draft",
                "summary": "Updated summary",
                "bill_text": "Section 1. Require disclosure by 2027.",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "In drafting"

        refreshed = client.post(f"/api/projects/{project_id}/insights/refresh", headers=headers)
        assert refreshed.status_code == 200
        assert refreshed.json()["drafting_focus"]["next_actions"] == ["Narrow enforcement scope"]

        agent = client.post(
            f"/api/projects/{project_id}/agent",
            headers=headers,
            json={"message": "Find the main conflicts."},
        )
        assert agent.status_code == 200
        assert agent.json()["suggested_stage"] == "Review"
        assert agent.json()["message"]["content"] == "Agent reviewed: Find the main conflicts."
