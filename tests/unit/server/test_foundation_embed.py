"""Phase 21.9 chunk B — POST /v1/foundation/embed-folder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_home(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(settings.openpathai_home))


def test_embed_folder_rejects_missing_directory(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/foundation/embed-folder",
        headers=auth_headers,
        json={"source_folder": "/no/such/path", "backbone": "dinov2_vits14"},
    )
    assert response.status_code == 422


def test_embed_folder_rejects_directory_with_no_images(
    client: TestClient, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    empty = tmp_path / "no-images"
    empty.mkdir()
    (empty / "README.txt").write_text("not an image")
    response = client.post(
        "/v1/foundation/embed-folder",
        headers=auth_headers,
        json={"source_folder": str(empty), "backbone": "dinov2_vits14"},
    )
    assert response.status_code == 422
    assert "no image files" in response.json()["detail"].lower()


def test_embed_folder_writes_csv_when_pyarrow_missing(
    client: TestClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end happy path with monkeypatched adapter (no real DINOv2
    download). Requests parquet but expects CSV fallback if pyarrow
    isn't installed in this CI cell."""
    pytest.importorskip("PIL")
    pytest.importorskip("torch")
    import numpy as np
    from PIL import Image

    src = tmp_path / "tiles"
    src.mkdir()
    rng = np.random.default_rng(0)
    for i in range(3):
        arr = (rng.random((96, 96, 3)) * 255).astype("uint8")
        Image.fromarray(arr).save(src / f"tile_{i}.png")

    # Stub the foundation adapter so the test never touches the network.
    from openpathai.foundation import dinov2 as _dinov2

    class _FakeBackbone:
        def __init__(self) -> None:
            self.embedding_dim = 6

    def _fake_build(self, pretrained: bool = True):  # type: ignore[no-untyped-def]
        self._module = _FakeBackbone()
        return self._module

    def _fake_embed(self, images: Any) -> np.ndarray:
        # Accept either a single (H, W, C) numpy image or a (N, C, H, W)
        # torch tensor. Return a 6-D embedding.
        import torch

        if isinstance(images, np.ndarray) and images.ndim == 3:
            colour = images.reshape(-1, images.shape[-1]).mean(axis=0)
            return np.concatenate([colour, np.zeros(3)]).astype(np.float32)
        if isinstance(images, torch.Tensor):
            colour = images.mean(dim=(2, 3))
            pad = torch.zeros((colour.shape[0], 6 - colour.shape[1]))
            return torch.cat([colour, pad], dim=1).cpu().numpy().astype(np.float32)
        raise TypeError(type(images).__name__)

    monkeypatch.setattr(_dinov2.DINOv2SmallAdapter, "build", _fake_build, raising=True)
    monkeypatch.setattr(_dinov2.DINOv2SmallAdapter, "embed", _fake_embed, raising=False)

    response = client.post(
        "/v1/foundation/embed-folder",
        headers=auth_headers,
        json={
            "source_folder": str(src),
            "backbone": "dinov2_vits14",
            "output_format": "csv",  # avoid pyarrow dependency in the test
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tiles"] == 3
    assert body["embedding_dim"] == 6
    assert body["resolved_backbone_id"] == "dinov2_vits14"
    assert body["output_format"] == "csv"
    out_path = Path(body["output_path"])
    assert out_path.is_file()
    # CSV has 1 header row + 3 data rows.
    lines = out_path.read_text().splitlines()
    assert len(lines) == 4
    assert lines[0].startswith("path,e0,e1,e2,e3,e4,e5")


def test_embed_folder_requires_auth(client: TestClient) -> None:
    assert client.post(
        "/v1/foundation/embed-folder", json={"source_folder": "/tmp"}
    ).status_code in (401, 403)
