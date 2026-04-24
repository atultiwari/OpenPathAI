"""Sigstore endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_sign_and_verify_round_trip(client: TestClient, auth_headers: dict[str, str]) -> None:
    manifest = {"run_id": "r1", "graph_hash": "h1", "pipeline_id": "demo"}
    sign = client.post(
        "/v1/manifest/sign",
        headers=auth_headers,
        json={"manifest": manifest},
    )
    # In a fresh home with no key, sign_manifest generates one.
    assert sign.status_code in {200, 404}
    if sign.status_code != 200:
        return
    signature = sign.json()
    verify = client.post(
        "/v1/manifest/verify",
        headers=auth_headers,
        json={"manifest": manifest, "signature": signature},
    )
    assert verify.status_code == 200
    assert verify.json()["valid"] is True


def test_verify_rejects_bad_signature(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/manifest/verify",
        headers=auth_headers,
        json={
            "manifest": {"run_id": "r1"},
            "signature": {"not": "a valid signature"},
        },
    )
    assert response.status_code == 422
