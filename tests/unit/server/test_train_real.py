"""Phase 21 refinement #1 — train route emits real metric points."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


def _wait_for_success(
    client: TestClient, headers: dict[str, str], run_id: str, *, timeout: float = 5.0
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/v1/train/runs/{run_id}/metrics", headers=headers)
        assert response.status_code == 200
        last = response.json()
        if last.get("status") == "success":
            return last
        if last.get("status") == "error":
            raise AssertionError(f"train job errored: {last.get('error')}")
        time.sleep(0.05)
    raise AssertionError(f"train job did not finish: {last}")


def test_synthetic_train_emits_metric_points(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    submit = client.post(
        "/v1/train",
        headers=auth_headers,
        json={
            "dataset": "lc25000-synth",
            "model": "resnet18",
            "epochs": 4,
            "synthetic": True,
        },
    )
    assert submit.status_code == 202, submit.text
    run_id = submit.json()["run_id"]
    metrics = _wait_for_success(client, auth_headers, run_id)
    epochs = metrics.get("epochs")
    assert isinstance(epochs, list)
    assert len(epochs) == 4
    # Loss should monotonically decrease (synthetic curve is exponential).
    losses = [e["train_loss"] for e in epochs]
    assert losses[0] > losses[-1]
    # Best record always present.
    assert metrics.get("best") is not None
    assert metrics.get("mode") == "synthetic"


def test_real_train_path_when_train_extra_present(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """When ``[train]`` is installed (CI matrix's ``server-train`` cell)
    the real Lightning path must produce one ``EpochRecord`` per epoch.

    Skip the test when torch/timm aren't importable so the suite stays
    green on the no-extras CI cells."""
    pytest.importorskip("torch")
    pytest.importorskip("timm")

    submit = client.post(
        "/v1/train",
        headers=auth_headers,
        json={
            "dataset": "ad-hoc",
            "model": "resnet18",
            "epochs": 1,
            "batch_size": 4,
            "synthetic": False,
        },
    )
    assert submit.status_code == 202, submit.text
    run_id = submit.json()["run_id"]
    metrics = _wait_for_success(client, auth_headers, run_id, timeout=60.0)
    assert metrics.get("mode") == "lightning"
    assert metrics.get("epochs")
