"""Tests for :mod:`openpathai.data.download`."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from openpathai.data.download import KaggleDownloader, kaggle_credentials_path


@pytest.mark.unit
def test_import_does_not_require_kaggle_package() -> None:
    # Module must be importable without the `kaggle` package available.
    # If any import-time hard dep on kaggle slipped in, this test would
    # have failed long before now.
    assert KaggleDownloader.default().cache_root.name == "datasets"


@pytest.mark.unit
def test_target_dir_normalises_slashes(tmp_path: Path) -> None:
    dl = KaggleDownloader(cache_root=tmp_path)
    target = dl.target_dir("owner/dataset")
    assert target.parent == tmp_path
    assert "/" not in target.name


@pytest.mark.unit
def test_download_requires_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path / "missing"))
    dl = KaggleDownloader(cache_root=tmp_path / "cache")
    with pytest.raises(FileNotFoundError, match="Kaggle credentials"):
        dl.download("owner/ds")


@pytest.mark.unit
def test_download_raises_import_error_when_package_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Place a dummy kaggle.json so the credentials check passes and
    # we hit the lazy import.
    creds_dir = tmp_path / "kagglecreds"
    creds_dir.mkdir()
    (creds_dir / "kaggle.json").write_text('{"username": "x", "key": "y"}', encoding="utf-8")
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(creds_dir))

    original_import = __import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("kaggle"):
            raise ImportError("simulated missing kaggle")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    dl = KaggleDownloader(cache_root=tmp_path / "cache")
    with pytest.raises(ImportError, match="openpathai\\[kaggle\\]"):
        dl.download("owner/ds")


@pytest.mark.unit
def test_download_calls_api_when_kaggle_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    creds_dir = tmp_path / "kagglecreds"
    creds_dir.mkdir()
    (creds_dir / "kaggle.json").write_text('{"username": "x", "key": "y"}', encoding="utf-8")
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(creds_dir))

    calls: dict[str, object] = {}

    class FakeApi:
        def authenticate(self) -> None:
            calls["auth"] = True

        def dataset_download_files(self, slug: str, *, path: str, unzip: bool, quiet: bool) -> None:
            calls["slug"] = slug
            calls["path"] = path
            calls["unzip"] = unzip

    fake_module = types.ModuleType("kaggle.api.kaggle_api_extended")
    fake_module.KaggleApi = FakeApi  # type: ignore[attr-defined]
    fake_api_module = types.ModuleType("kaggle.api")
    fake_api_module.kaggle_api_extended = fake_module  # type: ignore[attr-defined]
    fake_root = types.ModuleType("kaggle")
    fake_root.api = fake_api_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "kaggle", fake_root)
    monkeypatch.setitem(sys.modules, "kaggle.api", fake_api_module)
    monkeypatch.setitem(sys.modules, "kaggle.api.kaggle_api_extended", fake_module)

    dl = KaggleDownloader(cache_root=tmp_path / "cache")
    result = dl.download("owner/ds")
    assert result == dl.target_dir("owner/ds")
    assert calls["slug"] == "owner/ds"
    assert calls["unzip"] is True


@pytest.mark.unit
def test_credentials_path_respects_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path))
    assert kaggle_credentials_path() == tmp_path / "kaggle.json"
