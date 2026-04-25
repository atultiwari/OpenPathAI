"""Phase 21 — /v1/audit/runs/{id}/full envelope."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


def test_audit_full_404_for_unknown(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/v1/audit/runs/missing-run/full", headers=auth_headers)
    assert response.status_code == 404


def test_audit_full_resolves_runtime_record(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Submit a synthetic train job, then look it up via the full
    audit envelope. The runtime record should be present even if
    the audit DB has no row for the synthetic loop."""
    submit = client.post(
        "/v1/train",
        headers=auth_headers,
        json={
            "dataset": "lc25000-synth",
            "model": "resnet18",
            "epochs": 2,
            "synthetic": True,
        },
    )
    assert submit.status_code == 202, submit.text
    run_id = submit.json()["run_id"]
    full = client.get(f"/v1/audit/runs/{run_id}/full", headers=auth_headers)
    assert full.status_code == 200
    body = full.json()
    assert body["run_id"] == run_id
    assert body["runtime"] is not None
    assert isinstance(body["analyses"], list)
