"""Phase 0 smoke tests for the CLI skeleton."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from openpathai import __version__
from openpathai.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_version_flag_prints_version() -> None:
    """`openpathai --version` prints the version and exits 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.stdout
    assert __version__ in result.stdout


@pytest.mark.unit
def test_hello_prints_live_message() -> None:
    """`openpathai hello` prints the Phase 0 liveness message."""
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0, result.stdout
    assert "Phase 0 foundation is live" in result.stdout


@pytest.mark.unit
def test_bare_invocation_shows_help() -> None:
    """Running ``openpathai`` with no args prints help (exit 0 or 2 is fine)."""
    result = runner.invoke(app, [])
    # Typer's `no_args_is_help=True` prints help and exits non-zero.
    assert "OpenPathAI" in result.stdout or "Usage" in result.stdout
