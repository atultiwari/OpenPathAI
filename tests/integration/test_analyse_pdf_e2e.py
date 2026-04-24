"""Integration: ``openpathai analyse --pdf`` end-to-end on a fixture tile.

Torch + ReportLab are required. Skipped cleanly when either is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("timm")
pytest.importorskip("reportlab")
pytest.importorskip("PIL")

from PIL import Image
from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


@pytest.fixture
def fixture_tile(tmp_path: Path) -> Path:
    import numpy as np

    rng = np.random.default_rng(0)
    arr = (rng.random((64, 64, 3)) * 255).astype("uint8")
    out = tmp_path / "tile.png"
    Image.fromarray(arr, mode="RGB").save(out, format="PNG")
    return out


@pytest.mark.integration
def test_analyse_pdf_end_to_end(
    fixture_tile: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))
    pdf = tmp_path / "report.pdf"
    out_dir = tmp_path / "analyse-output"
    result = runner.invoke(
        app,
        [
            "analyse",
            "--tile",
            str(fixture_tile),
            "--model",
            "resnet18",
            "--num-classes",
            "2",
            "--target-class",
            "0",
            "--target-layer",
            "layer4",
            "--explainer",
            "gradcam",
            "--output-dir",
            str(out_dir),
            "--device",
            "cpu",
            "--low",
            "0.3",
            "--high",
            "0.8",
            "--pdf",
            str(pdf),
            "--allow-uncalibrated",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert pdf.exists()
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert "report:" in result.stdout
    assert "decision:" in result.stdout
