"""Phase 21.8 chunk B — per-model status / size-estimate / download."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_hf_home(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point HF_HOME at a per-test tmp dir so we never touch the real
    user cache + the openpathai_home + the redaction whitelist play
    nicely together."""
    monkeypatch.setenv("OPENPATHAI_HOME", str(settings.openpathai_home))
    monkeypatch.setenv("HF_HOME", str(settings.openpathai_home / "hf-home"))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)


def test_get_model_status_returns_absent_when_cache_missing(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """dinov2_vits14 has hf_repo=timm/... — with a clean tmp HF_HOME
    the cache is empty and the route reports present=False."""
    response = client.get("/v1/models/dinov2_vits14/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "dinov2_vits14"
    assert body["present"] is False
    assert body["source"] == "huggingface"
    assert body["target_dir"] is not None


def test_get_model_status_picks_up_seeded_cache(
    client: TestClient, auth_headers: dict[str, str], settings
) -> None:
    """When we seed the cache directory the route reports present=True
    + a non-zero size."""
    repo = "timm/vit_small_patch14_dinov2.lvd142m"
    safe = "models--" + repo.replace("/", "--")
    seed_dir: Path = settings.openpathai_home / "hf-home" / "hub" / safe
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "model.safetensors").write_bytes(b"x" * 1024)
    (seed_dir / "config.json").write_bytes(b"{}")

    body = client.get("/v1/models/dinov2_vits14/status", headers=auth_headers).json()
    assert body["present"] is True
    assert body["file_count"] == 2
    assert body["size_bytes"] == 1026


def test_get_model_status_404_for_unknown(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/v1/models/no-such-model/status", headers=auth_headers).status_code == 404


def test_size_estimate_handles_missing_hf_repo(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """resnet18 is a timm classifier — no hf_repo on its card →
    size-estimate returns null with a ``reason``."""
    response = client.get("/v1/models/resnet18/size-estimate", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["hf_repo"] is None
    assert body["size_bytes"] is None
    assert "no hf_repo" in (body["reason"] or "")


def test_size_estimate_prefers_adapter_declared_size(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 21.9 chunk A2 — adapter-declared ``size_bytes`` wins over
    HF round-trips. Patch HfApi to a sentinel that fails the test if
    it's ever called."""
    pytest.importorskip("huggingface_hub")
    import huggingface_hub

    from openpathai.server.routes import models as _models

    _models._SIZE_ESTIMATE_CACHE.clear()

    class _ExplodingApi:
        def model_info(self, *_a: Any, **_kw: Any) -> Any:
            raise AssertionError(
                "HfApi.model_info must not be called when adapter declares size_bytes"
            )

    monkeypatch.setattr(huggingface_hub, "HfApi", _ExplodingApi)

    body = client.get("/v1/models/dinov2_vits14/size-estimate", headers=auth_headers).json()
    assert body["reason"] == "adapter-declared"
    assert body["size_bytes"] == 168_000_000


def test_size_estimate_caches_within_a_process(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second call must hit the in-process cache, not re-resolve the adapter."""
    from openpathai.server.routes import models as _models

    _models._SIZE_ESTIMATE_CACHE.clear()
    calls = {"n": 0}
    original = _models._adapter_declared_size

    def _counting(model_id: str) -> int | None:
        calls["n"] += 1
        return original(model_id)

    monkeypatch.setattr(_models, "_adapter_declared_size", _counting)

    client.get("/v1/models/dinov2_vits14/size-estimate", headers=auth_headers)
    client.get("/v1/models/dinov2_vits14/size-estimate", headers=auth_headers)
    client.get("/v1/models/dinov2_vits14/size-estimate", headers=auth_headers)
    assert calls["n"] == 1, "size-estimate route must hit the cache after the first call"


def test_download_model_short_circuits_on_already_present(
    client: TestClient, auth_headers: dict[str, str], settings
) -> None:
    """Pre-populate the cache, then POST /download — should not call
    adapter.build() and report ``already_present``."""
    repo = "timm/vit_small_patch14_dinov2.lvd142m"
    safe = "models--" + repo.replace("/", "--")
    seed_dir: Path = settings.openpathai_home / "hf-home" / "hub" / safe
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "model.safetensors").write_bytes(b"x" * 64)

    body = client.post("/v1/models/dinov2_vits14/download", headers=auth_headers).json()
    assert body["status"] == "already_present"
    assert body["size_bytes"] == 64


def test_download_model_calls_adapter_build_on_miss(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    settings,
) -> None:
    """Stub the adapter's ``build`` so the test doesn't actually touch
    timm/HF. After the build, seed the cache so the post-status check
    reports the new bytes."""
    from openpathai.foundation import dinov2 as _dinov2

    repo = "timm/vit_small_patch14_dinov2.lvd142m"
    safe = "models--" + repo.replace("/", "--")
    seed_dir: Path = settings.openpathai_home / "hf-home" / "hub" / safe
    build_calls = {"n": 0}

    def _fake_build(self, pretrained: bool = True):  # type: ignore[no-untyped-def]
        build_calls["n"] += 1
        seed_dir.mkdir(parents=True, exist_ok=True)
        (seed_dir / "model.safetensors").write_bytes(b"y" * 256)
        return object()

    monkeypatch.setattr(_dinov2.DINOv2SmallAdapter, "build", _fake_build, raising=True)

    body = client.post("/v1/models/dinov2_vits14/download", headers=auth_headers).json()
    assert build_calls["n"] == 1
    assert body["status"] == "downloaded"
    assert body["file_count"] == 1
    assert body["size_bytes"] == 256


def test_download_model_returns_missing_backend_envelope_on_importerror(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openpathai.foundation import dinov2 as _dinov2

    def _boom(self, pretrained: bool = True):  # type: ignore[no-untyped-def]
        raise ImportError("torch is required")

    monkeypatch.setattr(_dinov2.DINOv2SmallAdapter, "build", _boom, raising=True)

    body = client.post("/v1/models/dinov2_vits14/download", headers=auth_headers).json()
    assert body["status"] == "missing_backend"
    assert body["install_cmd"] == "uv sync --extra train"
    assert "torch" in (body["message"] or "")


def test_download_model_routes_require_auth(client: TestClient) -> None:
    assert client.get("/v1/models/dinov2_vits14/status").status_code in (401, 403)
    assert client.post("/v1/models/dinov2_vits14/download").status_code in (401, 403)
    assert client.get("/v1/models/dinov2_vits14/size-estimate").status_code in (401, 403)


def test_download_gated_stub_returns_gated_status(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """Phase 21.9 chunk A3 — Hibou (and the other gated stubs) raise
    ``GatedAccessError`` regardless of message text. The download route
    must classify by exception type, not by string-matching, and surface
    a helpful "Request access at ..." message."""
    body = client.post("/v1/models/hibou/download", headers=auth_headers).json()
    assert body["status"] == "gated"
    assert "huggingface.co/histai/hibou-B" in (body["message"] or "")
