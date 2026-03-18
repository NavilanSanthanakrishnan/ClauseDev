from uuid import uuid4

from fastapi.testclient import TestClient

from clauseai_backend.main import app


def _signup(client: TestClient) -> str:
    email = f"chat-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "strong-password-123", "display_name": "Chat User"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_thread_creation_and_reply() -> None:
    client = TestClient(app)
    token = _signup(client)

    thread_response = client.post(
        "/api/chat/threads",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Housing research"},
    )
    assert thread_response.status_code == 201, thread_response.text
    thread_id = thread_response.json()["thread_id"]

    message_response = client.post(
        f"/api/chat/threads/{thread_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Find housing bills and statutes I should inspect."},
    )
    assert message_response.status_code == 201, message_response.text
    payload = message_response.json()
    assert len(payload) == 2
    assert payload[0]["role"] == "user"
    assert payload[1]["role"] == "assistant"
    assert "Research response for" in payload[1]["content"]
