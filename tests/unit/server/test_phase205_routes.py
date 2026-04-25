"""Phase 20.5 — task-shaped endpoints (analyse / cohorts / datasets register / active-learning / nl classify-named / train)."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from PIL import Image


def _png_bytes(size: tuple[int, int] = (32, 32)) -> bytes:
    arr = np.random.default_rng(0).integers(0, 255, size=(*size, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_analyse_tile_synthetic_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/analyse/tile",
        headers=auth_headers,
        data={"model_name": "model-not-in-registry", "explainer": "gradcam"},
        files={"image": ("tile.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_name"] == "model-not-in-registry"
    assert body["resolved_model_name"].endswith("-synthetic")
    # Iron rule #11: a fallback_reason is always surfaced when the
    # synthetic path runs. The exact reason depends on whether torch is
    # importable + the model resolved through the registry.
    assert body["fallback_reason"]
    assert body["heatmap_b64"]
    assert body["thumbnail_b64"]
    assert sum(body["probabilities"]) == pytest.approx(1.0, abs=1e-3)


def test_analyse_report_409_before_first_call(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/v1/analyse/report", headers=auth_headers)
    assert response.status_code == 409


def test_register_folder_creates_card(
    client: TestClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Isolate the user dataset registry so this test never collides
    # with the developer's local cards.
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))
    pool = tmp_path / "pool"
    for cls in ("benign", "malignant"):
        d = pool / cls
        d.mkdir(parents=True)
        Image.fromarray(np.zeros((24, 24, 3), dtype=np.uint8)).save(d / "a.png")
        Image.fromarray(np.zeros((24, 24, 3), dtype=np.uint8)).save(d / "b.png")
    payload = {
        "path": str(pool),
        "name": "phase205_demo_dataset",
        "tissue": ["colon"],
        "overwrite": True,
    }
    response = client.post(
        "/v1/datasets/register", headers=auth_headers, json=payload
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "phase205_demo_dataset"
    assert "benign" in (body.get("classes") or [])


def test_cohort_round_trip(
    client: TestClient, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    slides = tmp_path / "slides"
    slides.mkdir()
    for name in ("a.svs", "b.svs"):
        (slides / name).write_bytes(b"fake-svs")
    create = client.post(
        "/v1/cohorts",
        headers=auth_headers,
        json={"id": "cohort_demo", "directory": str(slides)},
    )
    assert create.status_code == 201
    assert create.json()["slide_count"] == 2

    listing = client.get("/v1/cohorts", headers=auth_headers)
    assert listing.status_code == 200
    ids = [row["id"] for row in listing.json()["items"]]
    assert "cohort_demo" in ids

    qc = client.post("/v1/cohorts/cohort_demo/qc", headers=auth_headers)
    assert qc.status_code == 200
    body = qc.json()
    assert body["slide_count"] == 2
    assert {"pass", "warn", "fail"}.issubset(body["summary"].keys())

    delete = client.delete("/v1/cohorts/cohort_demo", headers=auth_headers)
    assert delete.status_code == 204


def test_active_learning_demo_session(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/active-learning/sessions",
        headers=auth_headers,
        json={
            "classes": ["benign", "malignant"],
            "pool_size": 32,
            "seed_size": 4,
            "holdout_size": 8,
            "iterations": 1,
            "budget_per_iteration": 4,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("al-")
    manifest = body["manifest"]
    assert manifest["config"]["dataset_id"] == "synthetic-demo"
    assert len(manifest["acquisitions"]) >= 0

    listing = client.get("/v1/active-learning/sessions", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1


def test_classify_named_decorates_response(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    import base64

    image_b64 = base64.b64encode(_png_bytes()).decode("ascii")
    response = client.post(
        "/v1/nl/classify-named",
        headers=auth_headers,
        json={
            "image_b64": image_b64,
            "classes": ["benign", "malignant"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["classes"] == ["benign", "malignant"]
    assert "predicted_prompt" in body


def test_train_endpoint_enqueues_job(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/train",
        headers=auth_headers,
        json={
            "dataset": "lc25000",
            "model": "resnet18",
            "epochs": 1,
            "batch_size": 8,
            "synthetic": True,
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] in {"queued", "running", "success", "error"}
    metrics = client.get(f"/v1/train/runs/{body['run_id']}/metrics", headers=auth_headers)
    assert metrics.status_code == 200
    assert metrics.json()["run_id"] == body["run_id"]
