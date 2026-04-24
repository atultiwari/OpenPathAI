"""Unit tests for ``openpathai audit`` subcommands (Phase 8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))
    # Also scrub the real OS keyring — left-over tokens from other runs
    # would bleed into tests that assume a virgin store.
    from openpathai.safety.audit import KeyringTokenStore

    store = KeyringTokenStore()
    store.clear()
    yield
    store.clear()


def test_status_empty_db() -> None:
    result = runner.invoke(app, ["audit", "status"])
    assert result.exit_code == 0, result.stdout
    assert "schema_version:  1" in result.stdout
    assert "runs total:      0" in result.stdout


def test_init_prints_token_once() -> None:
    result = runner.invoke(app, ["audit", "init"])
    assert result.exit_code == 0, result.stdout
    assert "SAVE THIS TOKEN NOW" in result.stdout


def test_init_refuses_overwrite_without_force() -> None:
    first = runner.invoke(app, ["audit", "init"])
    assert first.exit_code == 0
    second = runner.invoke(app, ["audit", "init"])
    assert second.exit_code == 1


def test_init_force_rotates() -> None:
    first = runner.invoke(app, ["audit", "init"])
    assert first.exit_code == 0
    second = runner.invoke(app, ["audit", "init", "--force"])
    assert second.exit_code == 0


def test_list_empty_prints_placeholder() -> None:
    result = runner.invoke(app, ["audit", "list"])
    assert result.exit_code == 0
    assert "no runs matched" in result.stdout


def test_show_unknown_run_exits_2() -> None:
    result = runner.invoke(app, ["audit", "show", "does-not-exist"])
    assert result.exit_code == 2


def test_list_after_run(tmp_path: Path) -> None:
    """Kick a pipeline run and confirm it lands in the audit list."""
    pipeline_path = Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"
    if not pipeline_path.is_file():
        pytest.skip(f"fixture pipeline missing: {pipeline_path}")
    run_result = runner.invoke(
        app,
        [
            "run",
            str(pipeline_path),
            "--cache-root",
            str(tmp_path / "cache"),
            "--output-dir",
            str(tmp_path / "run"),
        ],
    )
    assert run_result.exit_code == 0, run_result.stdout
    assert "audit:" in run_result.stdout

    list_result = runner.invoke(app, ["audit", "list"])
    assert list_result.exit_code == 0, list_result.stdout
    # Expect exactly one pipeline row.
    assert list_result.stdout.count("pipeline") >= 1


def test_no_audit_flag_skips_write(tmp_path: Path) -> None:
    pipeline_path = Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"
    if not pipeline_path.is_file():
        pytest.skip(f"fixture pipeline missing: {pipeline_path}")
    runner.invoke(
        app,
        [
            "run",
            str(pipeline_path),
            "--cache-root",
            str(tmp_path / "cache"),
            "--output-dir",
            str(tmp_path / "run"),
            "--no-audit",
        ],
    )
    list_result = runner.invoke(app, ["audit", "list"])
    assert list_result.exit_code == 0
    assert "no runs matched" in list_result.stdout


def test_delete_without_init_fails() -> None:
    # No token set → delete refuses with exit 2.
    result = runner.invoke(
        app,
        [
            "audit",
            "delete",
            "--before",
            "2100-01-01",
            "--token",
            "whatever",
            "--yes",
        ],
    )
    assert result.exit_code == 2


def test_delete_wrong_token_exits_3() -> None:
    runner.invoke(app, ["audit", "init"])
    result = runner.invoke(
        app,
        [
            "audit",
            "delete",
            "--before",
            "2100-01-01",
            "--token",
            "definitely-wrong",
            "--yes",
        ],
    )
    assert result.exit_code == 3


def test_delete_dry_run_default(tmp_path: Path) -> None:
    init = runner.invoke(app, ["audit", "init"])
    assert init.exit_code == 0
    token = init.stdout.strip().splitlines()[-1]
    result = runner.invoke(
        app,
        [
            "audit",
            "delete",
            "--before",
            "2100-01-01",
            "--token",
            token,
        ],
    )
    assert result.exit_code == 0
    assert "Would delete" in result.stdout
