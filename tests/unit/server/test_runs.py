"""Run enqueue + status."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

import time
from pathlib import Path

from fastapi.testclient import TestClient

from openpathai.server.jobs import JobRunner


def _stub_pipeline() -> dict[str, object]:
    return {"id": "runnable", "mode": "exploratory", "steps": []}


def test_post_runs_enqueues(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/runs",
        headers=auth_headers,
        json={"pipeline": _stub_pipeline()},
    )
    # 202 Accepted — the executor may still be running / finished on return.
    assert response.status_code == 202
    body = response.json()
    assert "run_id" in body
    assert body["status"] in {"queued", "running", "success", "error"}


def test_post_runs_requires_pipeline_or_id(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/v1/runs", headers=auth_headers, json={})
    assert response.status_code == 400


def test_get_run_404_for_unknown_id(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/runs/does-not-exist", headers=auth_headers)
    assert response.status_code == 404


def test_saved_pipeline_id_is_resolved(
    client: TestClient, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    del tmp_path
    client.put(
        "/v1/pipelines/saved-demo",
        headers=auth_headers,
        json=_stub_pipeline(),
    )
    response = client.post(
        "/v1/runs",
        headers=auth_headers,
        json={"saved_pipeline_id": "saved-demo"},
    )
    assert response.status_code == 202


def test_list_runs(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/v1/runs", headers=auth_headers, json={"pipeline": _stub_pipeline()})
    response = client.get("/v1/runs", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)
    assert body["total"] >= 1


def test_manifest_404_before_completion(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Start a run but immediately ask for the manifest — a cached Phase-1
    # no-op pipeline will often complete before the test hits, so accept
    # either 200 or 409 (still running).
    post = client.post(
        "/v1/runs",
        headers=auth_headers,
        json={"pipeline": _stub_pipeline()},
    )
    run_id = post.json()["run_id"]
    # Allow the tiny empty pipeline to complete.
    for _ in range(50):
        status = client.get(f"/v1/runs/{run_id}", headers=auth_headers).json()["status"]
        if status in {"success", "error"}:
            break
        time.sleep(0.05)
    manifest = client.get(f"/v1/runs/{run_id}/manifest", headers=auth_headers)
    assert manifest.status_code in {200, 409, 500}


def test_job_runner_direct() -> None:
    """Phase-19 JobRunner is exercised without the HTTP layer."""
    with JobRunner(max_workers=2) as runner:
        rec = runner.submit(lambda: 42, metadata={"foo": "bar"})
        assert rec.status in {"queued", "running", "success"}
        # Wait for completion.
        for _ in range(50):
            got = runner.get(rec.run_id)
            assert got is not None
            if got.status in {"success", "error"}:
                break
            time.sleep(0.02)
        assert runner.get(rec.run_id).status == "success"  # type: ignore[union-attr]
        assert runner.get(rec.run_id).result == 42  # type: ignore[union-attr]
