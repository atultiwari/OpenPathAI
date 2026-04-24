"""Phase 10 — ``openpathai mlflow-ui`` CLI."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner()


def test_mlflow_ui_help_exits_zero() -> None:
    result = runner.invoke(app, ["mlflow-ui", "--help"])
    assert result.exit_code == 0, result.stdout
    out = strip_ansi(result.stdout)
    for token in ("--host", "--port", "--tracking-uri"):
        assert token in out, f"{token!r} missing from help output:\n{out}"


def test_mlflow_ui_without_extra_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate missing mlflow by monkeypatching importlib.util.find_spec."""
    import openpathai.cli.mlflow_cmd as mlflow_cmd

    def _no_mlflow(name: str):
        if name == "mlflow":
            return None
        return __import__("importlib.util", fromlist=["find_spec"]).find_spec(name)

    monkeypatch.setattr(mlflow_cmd.importlib.util, "find_spec", _no_mlflow)
    result = runner.invoke(app, ["mlflow-ui", "--host", "127.0.0.1"])
    assert result.exit_code == 3
    assert "[mlflow]" in result.stdout
