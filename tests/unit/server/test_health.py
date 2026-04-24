"""Health + version endpoints don't require auth."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["api_version"] == "v1"


def test_version_is_public(client: TestClient) -> None:
    response = client.get("/v1/version")
    assert response.status_code == 200
    body = response.json()
    assert "openpathai_version" in body
    assert body["api_version"] == "v1"


def test_openapi_schema_available(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "OpenPathAI API"
    paths = schema.get("paths", {})
    assert "/v1/health" in paths
    assert "/v1/nodes" in paths
    assert "/v1/runs" in paths
