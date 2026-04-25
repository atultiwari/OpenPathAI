"""Phase 21 — heatmap computation + DZI overlay."""

from __future__ import annotations

import io

import numpy as np
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from PIL import Image


def _png_bytes(size: tuple[int, int] = (96, 64)) -> bytes:
    arr = np.random.default_rng(3).integers(0, 255, size=(size[1], size[0], 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/v1/slides",
        headers=headers,
        files={"file": ("synth.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 201
    return response.json()["slide_id"]


def test_compute_heatmap_returns_summary(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    sid = _upload(client, auth_headers)
    response = client.post(
        "/v1/heatmaps",
        headers=auth_headers,
        json={
            "slide_id": sid,
            "model_name": "resnet18",
            "classes": ["benign", "malignant"],
            "tile_grid": 8,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["heatmap_id"].startswith("hm_")
    assert body["slide_id"] == sid
    assert body["resolved_model_name"].endswith("-synthetic")
    # Iron rule #11.
    assert body["fallback_reason"]
    assert body["dzi_url"].endswith(".dzi")


def test_heatmap_dzi_descriptor_and_tile(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    sid = _upload(client, auth_headers)
    create = client.post(
        "/v1/heatmaps",
        headers=auth_headers,
        json={
            "slide_id": sid,
            "model_name": "heuristic-synthetic",
            "classes": ["a", "b", "c"],
            "tile_grid": 6,
        },
    )
    hid = create.json()["heatmap_id"]
    descriptor = client.get(create.json()["dzi_url"], headers=auth_headers)
    assert descriptor.status_code == 200
    assert b"Image" in descriptor.content
    # Top-of-pyramid level for any image is 0; this tile must exist.
    tile = client.get(
        f"/v1/heatmaps/{hid}_files/0/0_0.png", headers=auth_headers
    )
    assert tile.status_code == 200
    assert tile.headers["content-type"] == "image/png"


def test_compute_heatmap_404_when_slide_missing(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/heatmaps",
        headers=auth_headers,
        json={"slide_id": "deadbeef" * 8, "classes": ["a", "b"]},
    )
    assert response.status_code == 404


def test_list_then_delete_heatmap(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    sid = _upload(client, auth_headers)
    create = client.post(
        "/v1/heatmaps",
        headers=auth_headers,
        json={"slide_id": sid, "classes": ["x", "y"], "tile_grid": 4},
    )
    hid = create.json()["heatmap_id"]
    listing = client.get("/v1/heatmaps", headers=auth_headers, params={"slide_id": sid})
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    delete = client.delete(f"/v1/heatmaps/{hid}", headers=auth_headers)
    assert delete.status_code == 204
    follow = client.get(f"/v1/heatmaps/{hid}", headers=auth_headers)
    assert follow.status_code == 404
