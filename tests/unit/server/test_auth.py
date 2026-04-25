"""Bearer-token dependency."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from openpathai.server.auth import _extract_bearer


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get("/v1/nodes")
    assert response.status_code == 401
    body = response.json()
    assert "detail" in body
    assert body.get("code") == "http_401"


def test_wrong_token_returns_401(client: TestClient) -> None:
    response = client.get("/v1/nodes", headers={"Authorization": "Bearer totally-wrong"})
    assert response.status_code == 401


def test_valid_token_passes(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/nodes", headers=auth_headers)
    assert response.status_code == 200


def test_query_token_passes(client: TestClient) -> None:
    """Phase 21 — ``?token=<bearer>`` accepted as a fallback so the
    OpenSeadragon viewer's image tile fetches can authenticate without
    a custom header."""
    from tests.unit.server.conftest import TEST_TOKEN

    response = client.get(f"/v1/nodes?token={TEST_TOKEN}")
    assert response.status_code == 200


def test_query_token_wrong_returns_401(client: TestClient) -> None:
    response = client.get("/v1/nodes?token=wrong")
    assert response.status_code == 401


def test_extract_bearer_helper() -> None:
    assert _extract_bearer("Bearer abc") == "abc"
    assert _extract_bearer("bearer abc") == "abc"  # case-insensitive scheme
    assert _extract_bearer("Bearer   padded ") == "padded"
    assert _extract_bearer(None) is None
    assert _extract_bearer("") is None
    assert _extract_bearer("Basic abc") is None
    assert _extract_bearer("Bearer") is None
