"""Phase 11 — ``openpathai export-colab`` CLI tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app
from openpathai.safety.audit import AuditDB

runner = CliRunner(mix_stderr=False)


def _shipped_yaml() -> Path:
    return Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))


def test_export_colab_with_pipeline_only(tmp_path: Path) -> None:
    out = tmp_path / "run.ipynb"
    result = runner.invoke(
        app,
        [
            "export-colab",
            "--pipeline",
            str(_shipped_yaml()),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert out.is_file()
    nb = json.loads(out.read_text())
    assert nb["nbformat"] == 4
    assert nb["metadata"]["openpathai"]["source_run_id"] == ""
    # The install cell should pin a version.
    install_src = "".join(nb["cells"][1]["source"])
    assert "%pip install" in install_src
    assert "openpathai" in install_src


def test_export_colab_with_version_override(tmp_path: Path) -> None:
    out = tmp_path / "run.ipynb"
    result = runner.invoke(
        app,
        [
            "export-colab",
            "--pipeline",
            str(_shipped_yaml()),
            "--out",
            str(out),
            "--openpathai-version",
            "9.9.9",
        ],
    )
    assert result.exit_code == 0, result.stdout
    nb = json.loads(out.read_text())
    assert nb["metadata"]["openpathai"]["pip_spec"] == "openpathai==9.9.9"


def test_export_colab_embeds_run_id_lineage(tmp_path: Path) -> None:
    db = AuditDB.open_default()
    entry = db.insert_run(
        kind="pipeline",
        pipeline_yaml_hash="zzz",
        graph_hash="yyy",
        manifest_path="",
    )
    out = tmp_path / "run.ipynb"
    result = runner.invoke(
        app,
        [
            "export-colab",
            "--pipeline",
            str(_shipped_yaml()),
            "--run-id",
            entry.run_id,
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout
    nb = json.loads(out.read_text())
    assert nb["metadata"]["openpathai"]["source_run_id"] == entry.run_id


def test_export_colab_without_pipeline_or_run_id(tmp_path: Path) -> None:
    out = tmp_path / "run.ipynb"
    result = runner.invoke(app, ["export-colab", "--out", str(out)])
    assert result.exit_code == 2
    assert "--pipeline" in result.stdout or "--pipeline" in (result.stderr or "")


def test_export_colab_unknown_run_id(tmp_path: Path) -> None:
    out = tmp_path / "run.ipynb"
    result = runner.invoke(
        app,
        [
            "export-colab",
            "--pipeline",
            str(_shipped_yaml()),
            "--run-id",
            "run-does-not-exist",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "No audit run" in combined


def test_export_colab_run_id_without_pipeline_errors(tmp_path: Path) -> None:
    db = AuditDB.open_default()
    entry = db.insert_run(kind="pipeline", manifest_path="")

    out = tmp_path / "run.ipynb"
    result = runner.invoke(
        app,
        [
            "export-colab",
            "--run-id",
            entry.run_id,
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "--pipeline" in combined
