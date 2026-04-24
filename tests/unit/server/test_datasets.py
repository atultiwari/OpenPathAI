"""Dataset registry route."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_datasets_returns_registry(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/datasets", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)
    assert body["total"] == len(body["items"])


def test_unknown_dataset_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/datasets/not_a_real_dataset", headers=auth_headers)
    assert response.status_code == 404
