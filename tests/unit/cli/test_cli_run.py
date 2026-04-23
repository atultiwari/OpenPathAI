"""Integration-ish CLI tests for ``openpathai run``.

Uses the torch-free demo YAML shipped in the repo so these pass on any
Python install.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


def _shipped_yaml() -> Path:
    return Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"


@pytest.mark.unit
def test_run_demo_yaml_writes_manifest(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    out = tmp_path / "run"
    result = runner.invoke(
        app,
        [
            "run",
            str(_shipped_yaml()),
            "--cache-root",
            str(cache),
            "--output-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["pipeline_id"] == "demo-smoke"
    assert len(manifest["steps"]) == 3
    artifacts = json.loads((out / "artifacts.json").read_text())
    assert set(artifacts.keys()) == {"source", "doubled", "average"}


@pytest.mark.unit
def test_run_rejects_missing_yaml(tmp_path: Path) -> None:
    result = runner.invoke(app, ["run", str(tmp_path / "missing.yaml")])
    # Typer Argument(exists=True) catches this with exit code 2.
    assert result.exit_code == 2


@pytest.mark.unit
def test_run_rejects_malformed_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- not a mapping\n")
    result = runner.invoke(
        app,
        ["run", str(bad), "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code == 2


@pytest.mark.unit
def test_run_cache_hits_on_rerun(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    runner.invoke(
        app,
        [
            "run",
            str(_shipped_yaml()),
            "--cache-root",
            str(cache),
            "--output-dir",
            str(tmp_path / "first"),
        ],
    )
    second = runner.invoke(
        app,
        [
            "run",
            str(_shipped_yaml()),
            "--cache-root",
            str(cache),
            "--output-dir",
            str(tmp_path / "second"),
        ],
    )
    assert second.exit_code == 0, second.stdout
    assert "hits=3 misses=0" in second.stdout
