"""Phase 21 — wiring smoke + browser-oracle corrections endpoint."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


def test_phase21_routers_listed_in_openapi(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths: list[str] = list(response.json()["paths"].keys())
    must_include = (
        "/v1/slides",
        "/v1/heatmaps",
        "/v1/audit/runs/{run_id}/full",
        "/v1/cohorts/{cohort_id}/qc.html",
        "/v1/cohorts/{cohort_id}/qc.pdf",
        "/v1/active-learning/sessions/{session_id}/corrections",
    )
    for fragment in must_include:
        assert fragment in paths, f"missing {fragment} in OpenAPI: {sorted(paths)}"


def test_browser_oracle_corrections_round_trip(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # First start a synthetic session so a directory exists for us.
    start = client.post(
        "/v1/active-learning/sessions",
        headers=auth_headers,
        json={
            "classes": ["benign", "malignant"],
            "pool_size": 16,
            "seed_size": 4,
            "holdout_size": 4,
            "iterations": 1,
            "budget_per_iteration": 2,
        },
    )
    assert start.status_code == 201, start.text
    session_id = start.json()["id"]

    submit = client.post(
        f"/v1/active-learning/sessions/{session_id}/corrections",
        headers=auth_headers,
        json={
            "annotator_id": "browser-test",
            "corrections": [
                {
                    "tile_id": "tile-0001",
                    "predicted_label": "benign",
                    "corrected_label": "malignant",
                    "iteration": 0,
                },
                {
                    "tile_id": "tile-0002",
                    "predicted_label": "benign",
                    "corrected_label": "benign",
                    "iteration": 0,
                },
            ],
        },
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["written"] == 2
    assert body["annotator_id"] == "browser-test"


def test_browser_oracle_404_for_missing_session(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/active-learning/sessions/nonexistent/corrections",
        headers=auth_headers,
        json={
            "annotator_id": "x",
            "corrections": [{"tile_id": "t-1", "corrected_label": "y"}],
        },
    )
    assert response.status_code == 404
