"""KeyringTokenStore — init + verify + file fallback + clear."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.safety.audit import KeyringTokenStore
from openpathai.safety.audit.token import _token_fallback_path


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))


def test_init_returns_token_and_backend() -> None:
    store = KeyringTokenStore()
    store.clear()
    token, backend = store.init()
    assert len(token) >= 16
    assert backend in {"keyring", "file"}


def test_verify_matches_generated_token() -> None:
    store = KeyringTokenStore()
    store.clear()
    token, _ = store.init()
    assert store.verify(token) is True
    assert store.verify("wrong") is False
    assert store.verify("") is False


def test_status_reports_set_after_init() -> None:
    store = KeyringTokenStore()
    store.clear()
    status = store.status()
    assert status["set"] == "false"
    store.init()
    status = store.status()
    assert status["set"] == "true"
    assert status["store"] in {"keyring", "file"}


def test_clear_forgets_token() -> None:
    store = KeyringTokenStore()
    store.clear()
    token, _ = store.init()
    assert store.verify(token) is True
    store.clear()
    assert store.verify(token) is False


def test_file_fallback_when_keyring_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force every keyring call to raise; store must fall back to file."""

    class _BrokenKeyring:
        @staticmethod
        def set_password(*_a, **_kw):
            raise RuntimeError("no D-Bus")

        @staticmethod
        def get_password(*_a, **_kw):
            raise RuntimeError("no D-Bus")

        @staticmethod
        def delete_password(*_a, **_kw):
            raise RuntimeError("no D-Bus")

    monkeypatch.setitem(__import__("sys").modules, "keyring", _BrokenKeyring())

    store = KeyringTokenStore()
    store.clear()  # should not raise even when keyring is broken
    token, backend = store.init()
    assert backend == "file"
    fallback = _token_fallback_path()
    assert fallback.is_file()
    # Mode 0o600 on POSIX (Windows chmod is advisory; skip the check there).
    import platform

    if platform.system() != "Windows":
        assert fallback.stat().st_mode & 0o777 == 0o600
    assert store.verify(token) is True
    assert store.verify("nope") is False
