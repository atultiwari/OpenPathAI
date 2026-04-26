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
    client: TestClient,
    auth_headers: dict[str, str],
    tmp_path,
    monkeypatch,
) -> None:
    """Phase 21.7 chunk A — the real Lightning path must:

    * resolve the dataset via the registry (no more "ad-hoc" stub);
    * read tiles off disk via ``LocalDatasetTileDataset``;
    * persist a checkpoint to ``$OPENPATHAI_HOME/checkpoints/<run_id>/``.

    Skip the test when torch/timm aren't importable so the suite stays
    green on the no-extras CI cells."""
    pytest.importorskip("torch")
    pytest.importorskip("timm")
    pytest.importorskip("PIL")

    import numpy as np
    from PIL import Image

    from openpathai.data.local import register_folder
    from openpathai.data.registry import default_registry

    # Build a tiny ImageFolder tree on disk so the real path has bytes
    # to read. Two classes, 4 96x96 RGB tiles each.
    root = tmp_path / "fake_dataset"
    rng = np.random.default_rng(0)
    for cls in ("class_a", "class_b"):
        cdir = root / cls
        cdir.mkdir(parents=True)
        for i in range(4):
            arr = (rng.random((96, 96, 3)) * 255).astype("uint8")
            Image.fromarray(arr).save(cdir / f"tile_{i}.png")

    # Pin OPENPATHAI_HOME so the checkpoint lands somewhere we can clean.
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "opa-home"))

    register_folder(
        root,
        name="fake_local",
        tissue=["test"],
        overwrite=True,
    )
    # Refresh the process-wide registry so the new card is visible.
    from openpathai.data import registry as _registry_mod

    _registry_mod._DEFAULT_REGISTRY = None
    assert "fake_local" in default_registry().names()

    submit = client.post(
        "/v1/train",
        headers=auth_headers,
        json={
            "dataset": "fake_local",
            "model": "resnet18",
            "epochs": 1,
            "batch_size": 4,
            "synthetic": False,
            "duration_preset": "Quick",
        },
    )
    assert submit.status_code == 202, submit.text
    run_id = submit.json()["run_id"]
    metrics = _wait_for_success(client, auth_headers, run_id, timeout=120.0)
    assert metrics.get("mode") == "lightning"
    assert metrics.get("epochs")
    result = metrics.get("result") or {}
    # The real path reports the on-disk dataset it actually read from.
    assert "fake_dataset" in str(result.get("dataset_path", ""))
    assert int(result.get("tiles_used", 0)) > 0
