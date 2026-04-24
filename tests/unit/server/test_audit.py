"""Audit-DB passthrough."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


def test_audit_runs_empty_on_fresh_home(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/audit/runs", headers=auth_headers, params={"limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)


def test_audit_runs_rejects_bad_kind(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/audit/runs", headers=auth_headers, params={"kind": "invalid-kind"})
    assert response.status_code == 422


def test_audit_run_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/audit/runs/nonexistent", headers=auth_headers)
    assert response.status_code == 404


def test_audit_analyses_filter_by_run_id(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/audit/analyses", headers=auth_headers, params={"run_id": "nope"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
