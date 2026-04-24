"""Pipeline CRUD."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _minimal_pipeline() -> dict[str, object]:
    return {
        "id": "demo",
        "mode": "exploratory",
        "steps": [],
    }


def test_put_and_get_round_trip(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _minimal_pipeline()
    response = client.put("/v1/pipelines/demo", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "demo"
    assert body["pipeline"]["id"] == "demo"
    assert body["graph_hash"]

    got = client.get("/v1/pipelines/demo", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["pipeline"]["id"] == "demo"


def test_put_rejects_bad_pipeline_id(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.put(
        "/v1/pipelines/..weird..",
        headers=auth_headers,
        json=_minimal_pipeline(),
    )
    assert response.status_code == 400


def test_list_paginates(client: TestClient, auth_headers: dict[str, str]) -> None:
    for name in ("alpha", "beta", "gamma"):
        payload = _minimal_pipeline()
        payload["id"] = name
        r = client.put(f"/v1/pipelines/{name}", headers=auth_headers, json=payload)
        assert r.status_code == 200
    response = client.get("/v1/pipelines", headers=auth_headers, params={"limit": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_delete_pipeline(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.put("/v1/pipelines/demo", headers=auth_headers, json=_minimal_pipeline())
    r = client.delete("/v1/pipelines/demo", headers=auth_headers)
    assert r.status_code == 204
    r2 = client.get("/v1/pipelines/demo", headers=auth_headers)
    assert r2.status_code == 404


def test_validate_reports_unknown_ops(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "id": "bad",
        "mode": "exploratory",
        "steps": [{"id": "s1", "op": "definitely_unknown_op", "inputs": {}}],
    }
    response = client.post("/v1/pipelines/validate", headers=auth_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["unknown_ops"] == ["definitely_unknown_op"]


def test_validate_rejects_schema_errors(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/pipelines/validate",
        headers=auth_headers,
        json={"id": "", "steps": "not-a-list"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"]
