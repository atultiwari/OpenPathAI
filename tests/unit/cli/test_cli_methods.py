"""``openpathai methods write`` CLI surface."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner(mix_stderr=False)


def test_methods_help() -> None:
    result = runner.invoke(app, ["methods", "--help"])
    assert result.exit_code == 0
    assert "write" in strip_ansi(result.stdout)


def test_methods_missing_manifest_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["methods", "write", str(tmp_path / "nope.json")],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "not found" in combined


def test_methods_malformed_manifest_exits_2(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    result = runner.invoke(app, ["methods", "write", str(bad)])
    assert result.exit_code == 2


def test_methods_without_backend_exits_3(tmp_path: Path) -> None:
    """CI cells have no Ollama / LM Studio → exit 3 + install message."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "run_id": "run-abc",
                "datasets": ["lc25000"],
                "models": ["resnet18"],
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["methods", "write", str(manifest)])
    assert result.exit_code == 3
    combined = result.stdout + (result.stderr or "")
    assert "No LLM backend" in combined or "backend is reachable" in combined
