"""Dataset registry route."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


def test_list_datasets_returns_registry(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/datasets", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)
    assert body["total"] == len(body["items"])


def test_unknown_dataset_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/datasets/not_a_real_dataset", headers=auth_headers)
    assert response.status_code == 404


# Phase 22.1 chunk C — /plan + /restructure routes.


def _make_two_class_imagefolder(root):
    pytest.importorskip("PIL")
    from PIL import Image  # type: ignore[import-untyped]

    for cls in ("a", "b"):
        for i in range(3):
            p = root / cls / f"{i}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (32, 32), (10, 20, 30)).save(p, format="PNG")
    return root


def test_inspect_returns_shape_tree(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    _make_two_class_imagefolder(tmp_path)
    r = client.post("/v1/datasets/inspect", json={"path": str(tmp_path)}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "class_bucket"
    assert {c["name"] for c in body["classes"]} == {"a", "b"}


def test_inspect_response_paths_are_not_phi_redacted(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    """Phase 22.1 regression: PHI middleware was rewriting the
    ``path`` and child paths returned by /inspect to ``basename#hash``,
    breaking the wizard's "Apply suggested path" loop. The bypass list
    in the middleware must keep these round-trippable."""
    _make_two_class_imagefolder(tmp_path)
    r = client.post("/v1/datasets/inspect", json={"path": str(tmp_path)}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # Real path comes back exactly — no `#hash` suffix.
    assert body["path"] == str(tmp_path.resolve())
    assert "#" not in body["path"]


def test_analyse_response_paths_are_not_phi_redacted(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    """Same regression for the legacy /analyse route."""
    _make_two_class_imagefolder(tmp_path)
    r = client.post("/v1/datasets/analyse", json={"path": str(tmp_path)}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["path"] == str(tmp_path.resolve())
    assert "#" not in body["path"]


def test_plan_for_classifier_returns_ok(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    _make_two_class_imagefolder(tmp_path)
    r = client.post(
        "/v1/datasets/plan",
        json={"path": str(tmp_path), "model_id": "tile-classifier-dinov2-small"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["requirement"] == "image_folder"
    assert body["actions"] == []


def test_plan_for_yolo_classifier_emits_split_actions(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    _make_two_class_imagefolder(tmp_path)
    r = client.post(
        "/v1/datasets/plan",
        json={"path": str(tmp_path), "model_id": "yolo-classifier-yolov26"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    kinds = {a["kind"] for a in body["actions"]}
    assert "make_dir" in kinds
    assert "make_split" in kinds
    assert "openpathai.cli.dataset split" in body["bash"]


def test_plan_for_yolo_detector_is_incompatible(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    _make_two_class_imagefolder(tmp_path)
    r = client.post(
        "/v1/datasets/plan",
        json={"path": str(tmp_path), "model_id": "yolo-detector-yolov26"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["actions"][0]["kind"] == "incompatible"


def test_restructure_dry_run_lists_actions_without_filesystem_writes(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    _make_two_class_imagefolder(tmp_path)
    r = client.post(
        "/v1/datasets/restructure",
        json={
            "path": str(tmp_path),
            "model_id": "yolo-classifier-yolov26",
            "dry_run": True,
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True
    assert any("make_split" in d for d in body["executed_actions"])
    # No yolo_cls_split dir got created on dry run.
    assert not (tmp_path.parent / f"{tmp_path.name}__yolo_cls_split").exists()


def test_restructure_commit_creates_split(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    _make_two_class_imagefolder(tmp_path)
    r = client.post(
        "/v1/datasets/restructure",
        json={
            "path": str(tmp_path),
            "model_id": "yolo-classifier-yolov26",
            "dry_run": False,
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is False
    assert body["errors"] == []
    new_root = body["new_root"]
    assert new_root is not None
    from pathlib import Path

    nr = Path(new_root)
    for split in ("train", "val", "test"):
        for cls in ("a", "b"):
            assert (nr / split / cls).is_dir()
