"""Node catalog."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_nodes_returns_catalog(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/nodes", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)
    assert body["total"] == len(body["items"])
    if body["items"]:
        first = body["items"][0]
        assert "id" in first
        assert "input_schema" in first
        assert "output_schema" in first
        assert "code_hash" in first


def test_unknown_node_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/nodes/not_a_real_node", headers=auth_headers)
    assert response.status_code == 404
