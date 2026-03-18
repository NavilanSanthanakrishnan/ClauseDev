from fastapi.testclient import TestClient

from clauseai_backend.main import app


def test_health_route_exists() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code in {200, 500}
