"""Unit tests for the ``openpathai cache`` subcommand."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app
from openpathai.pipeline.cache import ContentAddressableCache
from openpathai.pipeline.schema import IntArtifact

runner = CliRunner()


def _seed_cache(cache_root: Path) -> ContentAddressableCache:
    cache = ContentAddressableCache(root=cache_root)
    key = ContentAddressableCache.key(
        node_id="toy.seed",
        code_hash="0" * 64,
        input_config={"value": 1},
        upstream_hashes=[],
    )
    cache.put(
        key,
        node_id="toy.seed",
        code_hash="0" * 64,
        input_config={"value": 1},
        upstream_hashes=[],
        artifact=IntArtifact(value=1),
    )
    return cache


@pytest.mark.unit
def test_cache_show_on_empty_dir(tmp_path: Path) -> None:
    result = runner.invoke(app, ["cache", "show", "--cache-root", str(tmp_path / "empty")])
    assert result.exit_code == 0, result.stdout
    assert "entries:    0" in result.stdout


@pytest.mark.unit
def test_cache_show_after_seed(tmp_path: Path) -> None:
    _seed_cache(tmp_path)
    result = runner.invoke(app, ["cache", "show", "--cache-root", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert "entries:    1" in result.stdout


@pytest.mark.unit
def test_cache_clear_wipes_entries(tmp_path: Path) -> None:
    _seed_cache(tmp_path)
    result = runner.invoke(app, ["cache", "clear", "--cache-root", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    # A subsequent show should report zero entries.
    show = runner.invoke(app, ["cache", "show", "--cache-root", str(tmp_path)])
    assert "entries:    0" in show.stdout


@pytest.mark.unit
def test_cache_invalidate_missing_key_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["cache", "invalidate", "deadbeef", "--cache-root", str(tmp_path)],
    )
    assert result.exit_code == 1


@pytest.mark.unit
def test_cache_invalidate_existing_key_succeeds(tmp_path: Path) -> None:
    cache = _seed_cache(tmp_path)
    keys = list(cache.root.iterdir())
    assert keys, "seed failed"
    key = keys[0].name
    result = runner.invoke(
        app,
        ["cache", "invalidate", key, "--cache-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.stdout
