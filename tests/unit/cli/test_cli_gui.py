"""CLI tests for ``openpathai gui``."""

from __future__ import annotations

import importlib.util

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner()


@pytest.mark.unit
def test_gui_help_lists_host_port_share() -> None:
    result = runner.invoke(app, ["gui", "--help"])
    assert result.exit_code == 0, result.stdout
    out = strip_ansi(result.stdout)
    for token in ("--host", "--port", "--share", "--cache-root"):
        assert token in out, f"{token!r} missing from help output:\n{out}"


@pytest.mark.unit
def test_gui_without_gradio_exits_3() -> None:
    if importlib.util.find_spec("gradio") is not None:
        pytest.skip("gradio installed — this test covers the missing-gradio branch")
    result = runner.invoke(app, ["gui"])
    assert result.exit_code == 3
    out = strip_ansi(result.stdout)
    assert "[gui]" in out or "gradio" in out


@pytest.mark.unit
def test_gui_is_registered_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.stdout
    out = strip_ansi(result.stdout)
    assert "gui" in out
