"""Phase-20 canvas static mount."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from openpathai.server.app import create_app
from openpathai.server.config import ServerSettings

TOKEN = "canvas-test-token-123456789"


def _write_dist(root: Path) -> Path:
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("<html>canvas-stub</html>", encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "main.js").write_text("console.log('hi')", encoding="utf-8")
    return dist


def test_canvas_mount_serves_index(tmp_path: Path) -> None:
    dist = _write_dist(tmp_path)
    settings = ServerSettings(
        token=TOKEN,
        openpathai_home=tmp_path,
        pipelines_dir=tmp_path / "pipelines",
        canvas_dir=dist,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "canvas-stub" in root.text
        assets = client.get("/assets/main.js")
        assert assets.status_code == 200
        assert "console.log" in assets.text


def test_canvas_spa_fallback(tmp_path: Path) -> None:
    dist = _write_dist(tmp_path)
    settings = ServerSettings(
        token=TOKEN,
        openpathai_home=tmp_path,
        pipelines_dir=tmp_path / "pipelines",
        canvas_dir=dist,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        # Unknown SPA path falls back to index.html.
        deep = client.get("/runs/abc-123")
        assert deep.status_code == 200
        assert "canvas-stub" in deep.text
        # API routes still take precedence.
        health = client.get("/v1/health")
        assert health.status_code == 200


def test_canvas_mount_skipped_when_dir_missing(tmp_path: Path) -> None:
    settings = ServerSettings(
        token=TOKEN,
        openpathai_home=tmp_path,
        pipelines_dir=tmp_path / "pipelines",
        canvas_dir=tmp_path / "does-not-exist",
    )
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        app = create_app(settings)
        assert any("canvas_dir" in str(w.message) for w in caught)
    with TestClient(app) as client:
        # API still works.
        assert client.get("/v1/health").status_code == 200
        # Root is unmounted → 404.
        assert client.get("/").status_code == 404
