"""Tests for openpathai.config.hf — token resolution + on-disk file."""

from __future__ import annotations

import json
import stat
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from openpathai.config import hf


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point OPENPATHAI_HOME at a clean tmp dir and clear HF env vars."""
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))
    monkeypatch.delenv(hf.ENV_HF_TOKEN, raising=False)
    monkeypatch.delenv(hf.ENV_HF_HUB_TOKEN, raising=False)
    yield tmp_path


def test_resolve_returns_none_when_nothing_configured(isolated_home: Path) -> None:
    assert hf.resolve_token() is None
    assert hf.is_token_present() is False
    s = hf.status()
    assert s.present is False
    assert s.source == "none"
    assert s.token_preview is None


def test_set_token_writes_secrets_file_with_strict_mode(
    isolated_home: Path,
) -> None:
    path = hf.set_token("hf_supersecrettoken_42")
    assert path == isolated_home / hf.SECRETS_FILENAME
    assert path.is_file()

    payload = json.loads(path.read_text())
    assert payload == {"hf_token": "hf_supersecrettoken_42"}

    # Mode 0600 on POSIX. Skip on Windows where chmod is a no-op.
    if sys.platform != "win32":
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600, f"expected 0o600, got 0o{mode:o}"


def test_settings_file_wins_over_env(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(hf.ENV_HF_TOKEN, "from-env-hf")
    monkeypatch.setenv(hf.ENV_HF_HUB_TOKEN, "from-env-hub")
    hf.set_token("from-settings")
    assert hf.resolve_token() == "from-settings"
    s = hf.status()
    assert s.source == "settings"
    assert s.token_preview == "…ings"


def test_hf_token_env_wins_over_hub_token(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(hf.ENV_HF_TOKEN, "winner_abcd")
    monkeypatch.setenv(hf.ENV_HF_HUB_TOKEN, "loser_xyz")
    assert hf.resolve_token() == "winner_abcd"
    s = hf.status()
    assert s.source == "env_hf_token"
    assert s.token_preview == "…abcd"


def test_hub_token_env_when_only_one_present(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(hf.ENV_HF_HUB_TOKEN, "only_hub_abcd1234")
    assert hf.resolve_token() == "only_hub_abcd1234"
    s = hf.status()
    assert s.source == "env_hub_token"


def test_clear_token_removes_secrets_file_when_only_key(
    isolated_home: Path,
) -> None:
    path = hf.set_token("ephemeral")
    assert path.is_file()
    cleared = hf.clear_token()
    assert cleared is True
    assert not path.exists()
    assert hf.resolve_token() is None
    # Calling clear again is a no-op.
    assert hf.clear_token() is False


def test_clear_token_keeps_other_secrets(isolated_home: Path) -> None:
    path = hf.secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hf_token": "x", "other_key": "y"}))
    assert hf.clear_token() is True
    payload = json.loads(path.read_text())
    assert payload == {"other_key": "y"}


def test_set_token_rejects_empty(isolated_home: Path) -> None:
    with pytest.raises(ValueError):
        hf.set_token("   ")


def test_status_redacts_short_tokens(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(hf.ENV_HF_TOKEN, "abc")
    s = hf.status()
    # Even tokens shorter than 4 chars get redacted with the leading ellipsis.
    assert s.token_preview == "…abc"


def test_corrupt_secrets_file_treated_as_empty(isolated_home: Path) -> None:
    path = hf.secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json")
    assert hf.resolve_token() is None
    assert hf.status().source == "none"


def test_foundation_fallback_uses_resolver(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The legacy hf_token_present() in foundation.fallback must
    delegate to the resolver — proves Iron Rule #11 stays accurate
    after the canvas Settings card writes a token."""
    from openpathai.foundation import fallback

    # Fresh state.
    monkeypatch.delenv(hf.ENV_HF_TOKEN, raising=False)
    monkeypatch.delenv(hf.ENV_HF_HUB_TOKEN, raising=False)
    assert fallback.hf_token_present() is False

    # Settings file alone is enough — no env vars touched.
    hf.set_token("settings-only")
    assert fallback.hf_token_present() is True

    hf.clear_token()
    assert fallback.hf_token_present() is False
