from uuid import uuid4

from fastapi.testclient import TestClient

from clauseai_backend.main import app


def _signup(client: TestClient) -> str:
    email = f"workflow-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "strong-password-123", "display_name": "Workflow User"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_upload_metadata_and_analysis_flow() -> None:
    client = TestClient(app)
    token = _signup(client)

    project_response = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Clean Energy Implementation Act",
            "jurisdiction_type": "state",
            "jurisdiction_name": "California",
        },
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["project_id"]

    upload_response = client.post(
        f"/api/projects/{project_id}/source-document",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "bill.txt",
                b"SECTION 1. This act modernizes electric vehicle infrastructure and requires a phased implementation schedule.",
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 201, upload_response.text
    assert "electric vehicle infrastructure" in upload_response.json()["extracted_text"].lower()

    metadata_response = client.post(
        f"/api/projects/{project_id}/metadata/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert metadata_response.status_code == 200, metadata_response.text
    metadata_payload = metadata_response.json()
    assert metadata_payload["title"]
    assert metadata_payload["summary"]

    metadata_update_response = client.put(
        f"/api/projects/{project_id}/metadata",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Clean Energy Implementation Act",
            "description": "Updated description",
            "summary": "Updated summary",
            "keywords": ["clean-energy", "grid"],
            "extras": {
                "policy_area": "Energy",
                "affected_entities": ["utilities", "state agencies"],
            },
        },
    )
    assert metadata_update_response.status_code == 200, metadata_update_response.text
    assert metadata_update_response.json()["extras"]["policy_area"] == "Energy"

    similar_response = client.post(
        f"/api/projects/{project_id}/analysis/similar-bills",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert similar_response.status_code == 200, similar_response.text

    suggestions_response = client.get(
        f"/api/projects/{project_id}/suggestions/similar-bills",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert suggestions_response.status_code == 200, suggestions_response.text
    suggestions_payload = suggestions_response.json()
    assert len(suggestions_payload) >= 1
    assert suggestions_payload[0]["before_text"] == ""
    assert suggestions_payload[0]["after_text"] == ""

    save_response = client.post(
        f"/api/projects/{project_id}/draft/versions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "content_text": "SECTION 1. This act modernizes electric vehicle infrastructure and requires a phased implementation schedule.\nSECTION 2. The commission shall report annually.",
            "change_reason": "Add reporting section",
        },
    )
    assert save_response.status_code == 201, save_response.text
    assert save_response.json()["version_number"] >= 3

    suggestion_id = suggestions_payload[0]["suggestion_id"]
    apply_response = client.post(
        f"/api/projects/{project_id}/suggestion-items/{suggestion_id}/apply",
        headers={"Authorization": f"Bearer {token}"},
        json={"change_reason": "Apply suggested fix"},
    )
    assert apply_response.status_code == 400, apply_response.text
    assert apply_response.json()["detail"] == "Suggestion has no replacement text"

    versions_response = client.get(
        f"/api/projects/{project_id}/draft/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert versions_response.status_code == 200, versions_response.text
    assert len(versions_response.json()) >= 3

    editor_session_response = client.get(
        f"/api/projects/{project_id}/editor/session",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert editor_session_response.status_code == 200, editor_session_response.text
    assert editor_session_response.json() is None
