"""Model registry route."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_models_returns_flat_list(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/models", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)
    assert body["total"] == len(body["items"])
    kinds = {item["kind"] for item in body["items"]}
    # We expect entries from at least the classifier + foundation registries.
    assert "classifier" in kinds or "foundation" in kinds


def test_filter_by_kind(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/models", headers=auth_headers, params={"kind": "foundation"})
    assert response.status_code == 200
    body = response.json()
    for item in body["items"]:
        assert item["kind"] == "foundation"


def test_unknown_model_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/models/not_a_real_model", headers=auth_headers)
    assert response.status_code == 404
