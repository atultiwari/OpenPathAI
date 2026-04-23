"""CLI tests for ``openpathai gui``."""

from __future__ import annotations

import importlib.util

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_gui_help_lists_host_port_share() -> None:
    result = runner.invoke(app, ["gui", "--help"])
    assert result.exit_code == 0, result.stdout
    for token in ("--host", "--port", "--share", "--cache-root"):
        assert token in result.stdout


@pytest.mark.unit
def test_gui_without_gradio_exits_3() -> None:
    if importlib.util.find_spec("gradio") is not None:
        pytest.skip("gradio installed — this test covers the missing-gradio branch")
    result = runner.invoke(app, ["gui"])
    assert result.exit_code == 3
    # Typer prints a stripped-ANSI variant of the message.
    assert "[gui]" in result.stdout or "gradio" in result.stdout


@pytest.mark.unit
def test_gui_is_registered_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.stdout
    assert "gui" in result.stdout
