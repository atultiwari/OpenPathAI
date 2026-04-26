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
    pytest.importorskip("PIL")
    from PIL import Image

    name = _pick_zenodo_card(client, auth_headers)
    src = tmp_path / "user-data"
    # Phase 21.7 chunk C — auto-register requires an ImageFolder
    # layout (one subdir per class). Build one here so the symlink
    # both creates the on-disk symlink AND registers a usable card.
    for cls in ("class_a", "class_b"):
        cdir = src / cls
        cdir.mkdir(parents=True)
        for i in range(2):
            arr = bytes([(i * 7 + n) % 255 for n in range(96 * 96 * 3)])
            img = Image.frombytes("RGB", (96, 96), arr)
            img.save(cdir / f"tile_{i}.png")

    response = client.post(
        f"/v1/datasets/{name}/download",
        headers=auth_headers,
        json={"local_source_path": str(src)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "downloaded"
    assert body["method"] == "local"
    assert body["files_written"] == 4

    # The status endpoint immediately reflects the new state.
    status = client.get(f"/v1/datasets/{name}/status", headers=auth_headers).json()
    assert status["present"] is True
    assert status["files"] == 4


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


def test_local_source_auto_registers_a_local_card(
    client: TestClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    """Phase 21.7 chunk C — a local_source_path download must also write
    a `<original>_local` card to the registry so the train step can
    submit against the user's bytes immediately."""
    pytest.importorskip("PIL")
    from PIL import Image

    from openpathai.data import registry as _registry_mod
    from openpathai.data.registry import default_registry

    name = _pick_zenodo_card(client, auth_headers)
    src = tmp_path / "user-imagefolder"
    for cls in ("class_a", "class_b"):
        cdir = src / cls
        cdir.mkdir(parents=True)
        for i in range(2):
            Image.new("RGB", (96, 96), (i * 80, 40, 200 - i * 50)).save(cdir / f"tile_{i}.png")

    response = client.post(
        f"/v1/datasets/{name}/download",
        headers=auth_headers,
        json={"local_source_path": str(src)},
    )
    assert response.status_code == 200
    body = response.json()
    expected_card = f"{name}_local"
    assert body["registered_card"] == expected_card

    # The new card is visible to the train route immediately.
    _registry_mod._DEFAULT_REGISTRY = None
    reg = default_registry()
    assert expected_card in reg.names()
    new_card = reg.get(expected_card)
    assert new_card.download.method == "local"
    assert str(new_card.download.local_path) == str(src.resolve())


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
