"""Phase 11 — ``openpathai sync`` CLI tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app
from openpathai.safety.audit import AuditDB

runner = CliRunner(mix_stderr=False)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))


def _manifest(path: Path, run_id: str = "sync-run-1", **overrides: Any) -> Path:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "pipeline_id": "demo",
        "pipeline_graph_hash": "h" * 8,
        "timestamp_start": "2026-04-01T00:00:00+00:00",
        "timestamp_end": "2026-04-01T00:01:00+00:00",
        "mode": "exploratory",
        "environment": {"git_commit": "abc1234", "tier": "local"},
        "cache_stats": {"hits": 3, "misses": 1},
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_sync_imports_manifest(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "m.json")
    result = runner.invoke(app, ["sync", str(manifest)])
    assert result.exit_code == 0, result.stdout
    assert "Imported run sync-run-1" in result.stdout

    db = AuditDB.open_default()
    assert db.get_run("sync-run-1") is not None


def test_sync_show_is_dry_run(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "m.json", run_id="preview-only")
    result = runner.invoke(app, ["sync", str(manifest), "--show"])
    assert result.exit_code == 0, result.stdout

    payload = json.loads(result.stdout)
    assert payload["run_id"] == "preview-only"
    assert payload["kind"] == "pipeline"
    assert payload["git_commit"] == "abc1234"

    # --show must not write anything.
    db = AuditDB.open_default()
    assert db.get_run("preview-only") is None


def test_sync_is_idempotent(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "m.json", run_id="twice")
    first = runner.invoke(app, ["sync", str(manifest)])
    assert first.exit_code == 0, first.stdout
    second = runner.invoke(app, ["sync", str(manifest)])
    assert second.exit_code == 0, second.stdout

    db = AuditDB.open_default()
    matching = [r for r in db.list_runs() if r.run_id == "twice"]
    assert len(matching) == 1


def test_sync_rejects_missing_file(tmp_path: Path) -> None:
    # typer's `exists=True` on the argument means the CLI rejects this
    # before our importer ever runs.
    result = runner.invoke(app, ["sync", str(tmp_path / "nope.json")])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "does not exist" in combined or "Invalid value" in combined


def test_sync_rejects_malformed_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("garbage", encoding="utf-8")
    result = runner.invoke(app, ["sync", str(bad)])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "not a valid JSON" in combined


def test_sync_rejects_missing_required_fields(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"run_id": "x"}), encoding="utf-8")
    result = runner.invoke(app, ["sync", str(incomplete)])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "missing required" in combined
