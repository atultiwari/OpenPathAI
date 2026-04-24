"""Unit tests for ``openpathai diff`` (Phase 8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app
from openpathai.safety.audit import AuditDB

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))
    monkeypatch.setenv("NO_COLOR", "1")


def _seed_two_runs() -> tuple[str, str]:
    db = AuditDB.open_default()
    a = db.insert_run(
        kind="training",
        pipeline_yaml_hash="p-a",
        graph_hash="g-a",
        git_commit="aaa",
        status="success",
        metrics={"acc": 0.8},
        manifest_path="",
    )
    b = db.insert_run(
        kind="training",
        pipeline_yaml_hash="p-b",
        graph_hash="g-b",
        git_commit="bbb",
        status="failed",
        metrics={"acc": 0.7},
        manifest_path="",
    )
    return a.run_id, b.run_id


def test_diff_changed_fields() -> None:
    run_a, run_b = _seed_two_runs()
    result = runner.invoke(app, ["diff", run_a, run_b])
    assert result.exit_code == 0, result.stdout
    assert "status" in result.stdout
    assert "pipeline_yaml_hash" in result.stdout
    assert "metrics_json.acc" in result.stdout


def test_diff_identical_runs() -> None:
    run_a, _ = _seed_two_runs()
    result = runner.invoke(app, ["diff", run_a, run_a])
    assert result.exit_code == 0, result.stdout
    assert "No changes" in result.stdout


def test_diff_missing_run_exits_2() -> None:
    run_a, _ = _seed_two_runs()
    result = runner.invoke(app, ["diff", run_a, "does-not-exist"])
    assert result.exit_code == 2


def test_diff_no_ansi_when_no_color_set() -> None:
    run_a, run_b = _seed_two_runs()
    result = runner.invoke(app, ["diff", run_a, run_b])
    assert result.exit_code == 0
    assert "\x1b[" not in result.stdout


def test_diff_show_unchanged_flag() -> None:
    run_a, run_b = _seed_two_runs()
    result = runner.invoke(app, ["diff", run_a, run_b, "--show-unchanged"])
    assert result.exit_code == 0
    assert "Unchanged" in result.stdout
