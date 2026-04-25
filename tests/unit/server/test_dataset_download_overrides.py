"""Phase 21.6.1 — POST /v1/datasets/{name}/download override fields."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_dataset_root(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(settings.openpathai_home))


def _pick_zenodo_card(client: TestClient, headers: dict[str, str]) -> str:
    listing = client.get("/v1/datasets", headers=headers).json()
    return next(
        item["name"]
        for item in listing["items"]
        if item.get("download", {}).get("method") == "zenodo"
    )


def test_local_source_override_skips_the_network(
    client: TestClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    """Demonstrates the fix for the Zenodo-501 screenshot — the user
    can point at a folder they already populated by hand."""
    name = _pick_zenodo_card(client, auth_headers)
    src = tmp_path / "user-data"
    src.mkdir()
    (src / "tile_0.png").write_bytes(b"x" * 32)
    (src / "tile_1.png").write_bytes(b"y" * 64)

    response = client.post(
        f"/v1/datasets/{name}/download",
        headers=auth_headers,
        json={"local_source_path": str(src)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "downloaded"
    assert body["method"] == "local"
    assert body["files_written"] == 2

    # The status endpoint immediately reflects the new state.
    status = client.get(f"/v1/datasets/{name}/status", headers=auth_headers).json()
    assert status["present"] is True
    assert status["files"] == 2


def test_override_url_routes_through_url_downloader(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from openpathai.data import downloaders

    captured: dict[str, Any] = {}

    def fake_from_url(
        name: str, url: str, *, root: Path | None = None, method: str = "http"
    ) -> downloaders.DownloadResult:
        captured["name"] = name
        captured["url"] = url
        target = (root or tmp_path) / name
        target.mkdir(parents=True, exist_ok=True)
        return downloaders.DownloadResult(
            card_name=name,
            method=method,
            target_dir=target,
            files_written=1,
            bytes_written=128,
        )

    monkeypatch.setattr(downloaders, "download_from_url", fake_from_url)

    name = _pick_zenodo_card(client, auth_headers)
    response = client.post(
        f"/v1/datasets/{name}/download",
        headers=auth_headers,
        json={"override_url": "https://mirror.example.com/kather.zip"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "downloaded"
    assert body["files_written"] == 1
    assert captured["url"] == "https://mirror.example.com/kather.zip"


def test_override_huggingface_repo_routes_through_hf_downloader(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from openpathai.data import downloaders

    captured: dict[str, Any] = {}

    def fake_hf(
        card: Any,
        *,
        root: Path | None = None,
        subset: int | None = None,
        allow_patterns: Any = None,
    ) -> downloaders.DownloadResult:
        captured["repo"] = card.download.huggingface_repo
        captured["method"] = card.download.method
        target = (root or tmp_path) / card.name
        target.mkdir(parents=True, exist_ok=True)
        return downloaders.DownloadResult(
            card_name=card.name,
            method="huggingface",
            target_dir=target,
            files_written=10,
            bytes_written=1024,
        )

    monkeypatch.setattr(downloaders, "download_huggingface", fake_hf)

    name = _pick_zenodo_card(client, auth_headers)
    response = client.post(
        f"/v1/datasets/{name}/download",
        headers=auth_headers,
        json={"override_huggingface_repo": "1aurent/Colorectal-Histology-MNIST"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "downloaded"
    assert body["method"] == "huggingface"
    assert captured["repo"] == "1aurent/Colorectal-Histology-MNIST"
    assert captured["method"] == "huggingface"


def test_zenodo_method_now_routes_through_resolver(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Phase 21.6.1 fix for the API 501 in the screenshot — Zenodo
    cards must resolve to a URL and route through the http path."""
    from openpathai.data import downloaders

    captured: dict[str, str] = {}

    def fake_from_url(
        name: str, url: str, *, root: Path | None = None, method: str = "http"
    ) -> downloaders.DownloadResult:
        captured["url"] = url
        captured["method"] = method
        target = (root or tmp_path) / name
        target.mkdir(parents=True, exist_ok=True)
        return downloaders.DownloadResult(
            card_name=name,
            method=method,
            target_dir=target,
            files_written=1,
            bytes_written=64,
        )

    monkeypatch.setattr(downloaders, "download_from_url", fake_from_url)

    name = _pick_zenodo_card(client, auth_headers)
    response = client.post(
        f"/v1/datasets/{name}/download",
        headers=auth_headers,
        json={},
    )
    # No more 501 — the dispatcher resolves Zenodo to a URL.
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "downloaded"
    assert body["method"] == "zenodo"
    assert captured["url"].startswith("https://zenodo.org/record/")
