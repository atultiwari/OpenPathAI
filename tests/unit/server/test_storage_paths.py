"""Phase 21.6 chunk C — /v1/storage/paths."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_home(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(settings.openpathai_home))
    # Pin HF_HOME so the test never resolves to the real user home —
    # the PHI redaction middleware would otherwise rewrite absolute
    # paths under /Users/<name>/ on the way back, breaking assertions.
    monkeypatch.setenv("HF_HOME", str(settings.openpathai_home / "hf-cache"))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)


def test_storage_paths_returns_absolute_paths_for_every_field(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/v1/storage/paths", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    expected_keys = {
        "openpathai_home",
        "datasets",
        "models",
        "checkpoints",
        "dzi",
        "audit_db",
        "cache",
        "secrets",
        "hf_hub_cache",
        "pipelines",
    }
    assert set(body.keys()) == expected_keys
    for key, value in body.items():
        assert isinstance(value, str), key
        assert Path(value).is_absolute(), f"{key} -> {value!r} is not absolute"


def test_storage_paths_respects_openpathai_home(
    client: TestClient, auth_headers: dict[str, str], settings
) -> None:
    body = client.get("/v1/storage/paths", headers=auth_headers).json()
    home = Path(settings.openpathai_home)
    assert body["openpathai_home"] == str(home)
    assert body["datasets"] == str(home / "datasets")
    assert body["models"] == str(home / "models")
    assert body["checkpoints"] == str(home / "checkpoints")
    assert body["dzi"] == str(home / "dzi")
    assert body["audit_db"] == str(home / "audit.sqlite")
    assert body["cache"] == str(home / "cache")
    assert body["pipelines"] == str(home / "pipelines")
    assert body["secrets"] == str(home / "secrets.json")


def test_hf_hub_cache_honours_hf_home_env(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    custom = tmp_path / "hf-home"
    monkeypatch.setenv("HF_HOME", str(custom))
    body = client.get("/v1/storage/paths", headers=auth_headers).json()
    assert body["hf_hub_cache"] == str(custom / "hub")


def test_storage_paths_requires_auth(client: TestClient) -> None:
    assert client.get("/v1/storage/paths").status_code in (401, 403)


def test_phi_middleware_whitelists_library_paths(
    client: TestClient, auth_headers: dict[str, str], settings
) -> None:
    """Phase 21.7 chunk B regression — paths under $OPENPATHAI_HOME
    must round-trip *unredacted* so the user can copy them into a
    shell. Before the whitelist landed, an absolute path under
    /Users/<name>/... was rewritten to ``<basename>#<hash>`` even
    when the home was a tmp dir under /Users/me/.../tests."""
    body = client.get("/v1/storage/paths", headers=auth_headers).json()
    home = str(settings.openpathai_home)
    for key, value in body.items():
        assert "#" not in value, f"{key}={value!r} got PHI-redacted"
        if key == "openpathai_home":
            assert value == home
        elif key in {
            "datasets",
            "models",
            "checkpoints",
            "dzi",
            "cache",
            "pipelines",
            "audit_db",
            "secrets",
        }:
            assert value.startswith(home), f"{key}={value!r} not under {home}"


def test_phi_middleware_still_redacts_user_home_paths_outside_whitelist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitelist must not become a wildcard — a real /Users/.../Documents
    path (outside OPENPATHAI_HOME and HF_HOME) still gets redacted."""
    from openpathai.server.phi import _redact_string

    monkeypatch.setenv("OPENPATHAI_HOME", "/var/folders/xy/openpathai-test")
    monkeypatch.setenv("HF_HOME", "/var/folders/xy/hf-test")
    sensitive = "/Users/dr-smith/Documents/patient_x.dcm"
    redacted = _redact_string(sensitive)
    assert "patient_x.dcm" in redacted
    assert "#" in redacted
    assert "/Users/dr-smith" not in redacted
