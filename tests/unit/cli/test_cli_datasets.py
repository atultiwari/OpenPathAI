"""Unit tests for the ``openpathai datasets`` subcommand."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_datasets_list_includes_shipped_cards() -> None:
    result = runner.invoke(app, ["datasets", "list"])
    assert result.exit_code == 0, result.stdout
    for name in ("lc25000", "pcam", "mhist", "histai_breast", "histai_metadata"):
        assert name in result.stdout


@pytest.mark.unit
def test_datasets_list_modality_filter() -> None:
    result = runner.invoke(app, ["datasets", "list", "--modality", "wsi"])
    assert result.exit_code == 0
    assert "histai_breast" in result.stdout
    # LC25000 is tile-modality — must not appear under a WSI filter.
    assert "lc25000" not in result.stdout


@pytest.mark.unit
def test_datasets_list_no_match_exits_zero() -> None:
    result = runner.invoke(app, ["datasets", "list", "--tissue", "pancreas"])
    assert result.exit_code == 0
    assert "no dataset cards matched" in result.stdout


@pytest.mark.unit
def test_datasets_show_prints_yaml() -> None:
    result = runner.invoke(app, ["datasets", "show", "lc25000"])
    assert result.exit_code == 0, result.stdout
    assert "name: lc25000" in result.stdout


@pytest.mark.unit
def test_datasets_show_unknown_dataset_exits_2() -> None:
    result = runner.invoke(app, ["datasets", "show", "not-a-real-card"])
    assert result.exit_code == 2
