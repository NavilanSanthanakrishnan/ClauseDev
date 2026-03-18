from uuid import uuid4

from fastapi.testclient import TestClient

from clauseai_backend.main import app


def test_signup_and_create_project_flow() -> None:
    client = TestClient(app)
    email = f"test-{uuid4().hex[:8]}@example.com"
    password = "strong-password-123"

    signup_response = client.post(
        "/auth/signup",
        json={"email": email, "password": password, "display_name": "Test User"},
    )
    assert signup_response.status_code == 201, signup_response.text
    auth_payload = signup_response.json()
    token = auth_payload["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == email

    project_response = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Bill",
            "jurisdiction_type": "state",
            "jurisdiction_name": "California",
            "initial_text": "Section 1. Test draft.",
        },
    )
    assert project_response.status_code == 201, project_response.text
    project_payload = project_response.json()
    assert project_payload["title"] == "Test Bill"
    assert project_payload["current_stage"] == "upload"
