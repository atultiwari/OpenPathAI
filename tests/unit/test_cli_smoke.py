"""Smoke tests for the CLI skeleton (Phase 0 + Phase 3 extensions)."""

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
    assert "OpenPathAI" in result.stdout or "Usage" in result.stdout


@pytest.mark.unit
def test_models_list_includes_shipped_cards() -> None:
    result = runner.invoke(app, ["models", "list"])
    assert result.exit_code == 0, result.stdout
    assert "resnet18" in result.stdout
    assert "vit_small_patch16_224" in result.stdout


@pytest.mark.unit
def test_models_list_family_filter() -> None:
    result = runner.invoke(app, ["models", "list", "--family", "vit"])
    assert result.exit_code == 0, result.stdout
    assert "vit_small_patch16_224" in result.stdout
    # Swin is a different family even though both are transformers.
    assert "swin_tiny_patch4_window7_224" not in result.stdout


@pytest.mark.unit
def test_train_without_synthetic_flag_exits_with_guidance() -> None:
    result = runner.invoke(app, ["train", "--model", "resnet18", "--num-classes", "4"])
    assert result.exit_code == 2
    assert "Phase 5" in result.stdout
