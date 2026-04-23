"""Unit tests for the ``openpathai analyse`` subcommand."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_analyse_without_torch_emits_friendly_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If torch is absent, the command must exit cleanly with an ImportError msg."""
    if importlib.util.find_spec("torch") is not None:
        pytest.skip("torch installed — this test covers the missing-torch branch")
    tile = tmp_path / "tile.png"
    Image.fromarray(np.zeros((32, 32, 3), dtype=np.uint8)).save(tile)
    result = runner.invoke(
        app,
        [
            "analyse",
            "--tile",
            str(tile),
            "--model",
            "resnet18",
            "--num-classes",
            "2",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 3
    assert "torch" in result.stdout


@pytest.mark.unit
def test_analyse_unknown_model_exits_2(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    tile = tmp_path / "tile.png"
    Image.fromarray(np.zeros((32, 32, 3), dtype=np.uint8)).save(tile)
    result = runner.invoke(
        app,
        [
            "analyse",
            "--tile",
            str(tile),
            "--model",
            "not-a-real-card",
            "--num-classes",
            "2",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 2
