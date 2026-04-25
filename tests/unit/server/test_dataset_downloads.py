"""Phase 21.6 chunk B — /v1/datasets/{id}/download + /status routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_dataset_root(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the downloader root to the per-test tmp dir so a real
    ~/.openpathai/datasets is never touched by these tests."""
    monkeypatch.setenv("OPENPATHAI_HOME", str(settings.openpathai_home))


def test_status_returns_404_for_unknown_dataset(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/v1/datasets/no-such-dataset/status", headers=auth_headers)
    assert response.status_code == 404


def test_download_returns_404_for_unknown_dataset(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/datasets/no-such-dataset/download",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 404


def test_status_reports_absent_when_disk_is_empty(
    client: TestClient, auth_headers: dict[str, str], settings
) -> None:
    # Pick a real card from the registry.
    listing = client.get("/v1/datasets", headers=auth_headers).json()
    candidate = next(
        item["name"]
        for item in listing["items"]
        if item.get("download", {}).get("method") != "local"
    )
    response = client.get(f"/v1/datasets/{candidate}/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["dataset"] == candidate
    assert body["present"] is False
    assert body["files"] == 0
    assert body["bytes"] == 0
    expected_root = settings.openpathai_home / "datasets" / candidate
    assert body["target_dir"] == str(expected_root)


def test_dry_run_returns_describe_message(client: TestClient, auth_headers: dict[str, str]) -> None:
    listing = client.get("/v1/datasets", headers=auth_headers).json()
    candidate = next(
        item["name"]
        for item in listing["items"]
        if item.get("download", {}).get("method") not in ("local", "manual")
    )
    response = client.post(
        f"/v1/datasets/{candidate}/download",
        headers=auth_headers,
        json={"dry_run": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "skipped"
    assert candidate in (body["message"] or "")


def test_manual_dataset_surfaces_instructions(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """PCam ships with method=kaggle, but if a manual card is
    registered we should pass through its instructions_md instead of
    erroring."""
    listing = client.get("/v1/datasets", headers=auth_headers).json()
    manual_cards = [
        item for item in listing["items"] if item.get("download", {}).get("method") == "manual"
    ]
    if not manual_cards:
        pytest.skip("no manual-method card registered in this build")

    name = manual_cards[0]["name"]
    response = client.post(
        f"/v1/datasets/{name}/download",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "manual"
    assert body["files_written"] == 0


def test_missing_backend_returns_structured_payload(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When huggingface_hub is missing, the route returns 200 + a
    structured envelope rather than 500 — the wizard can then prompt
    the user to install the right extra."""
    from openpathai.data import downloaders

    def _boom(*_a: Any, **_kw: Any) -> Any:
        raise downloaders.MissingBackendError("The 'huggingface_hub' package is required.")

    monkeypatch.setattr(downloaders, "download_huggingface", _boom)

    listing = client.get("/v1/datasets", headers=auth_headers).json()
    hf_cards = [
        item for item in listing["items"] if item.get("download", {}).get("method") == "huggingface"
    ]
    if not hf_cards:
        pytest.skip("no huggingface-method card registered in this build")
    name = hf_cards[0]["name"]
    response = client.post(
        f"/v1/datasets/{name}/download",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing_backend"
    assert body["extra_required"] is not None
    assert "huggingface_hub" in (body["message"] or "")


def test_status_reflects_files_after_we_seed_some(
    client: TestClient, auth_headers: dict[str, str], settings
) -> None:
    """If something else (e.g. a previous download or a local-folder
    register) has populated the dataset dir, /status reports it."""
    listing = client.get("/v1/datasets", headers=auth_headers).json()
    candidate = next(
        item["name"]
        for item in listing["items"]
        if item.get("download", {}).get("method") not in ("local", "manual")
    )
    seed_dir: Path = settings.openpathai_home / "datasets" / candidate
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "tile_0.png").write_bytes(b"x" * 32)
    (seed_dir / "tile_1.png").write_bytes(b"y" * 64)

    body = client.get(f"/v1/datasets/{candidate}/status", headers=auth_headers).json()
    assert body["present"] is True
    assert body["files"] == 2
    assert body["bytes"] == 96


def test_download_routes_require_auth(client: TestClient) -> None:
    listing = client.get(
        "/v1/datasets", headers={"Authorization": "Bearer test-token-1234567890abcdef"}
    ).json()
    name = listing["items"][0]["name"]
    assert client.get(f"/v1/datasets/{name}/status").status_code in (401, 403)
    assert client.post(f"/v1/datasets/{name}/download", json={}).status_code in (401, 403)
