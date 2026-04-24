"""Integration: ``openpathai analyse`` writes exactly one audit row
whose ``image_sha256`` matches the fixture tile.

Torch + ReportLab gated; skipped cleanly without them.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("timm")
pytest.importorskip("reportlab")
pytest.importorskip("PIL")

from PIL import Image
from typer.testing import CliRunner

from openpathai.cli.main import app
from openpathai.safety.audit import AuditDB

runner = CliRunner()


@pytest.mark.integration
def test_analyse_pdf_and_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))
    import numpy as np

    rng = np.random.default_rng(0)
    arr = (rng.random((64, 64, 3)) * 255).astype("uint8")
    tile = tmp_path / "tile.png"
    Image.fromarray(arr, mode="RGB").save(tile, format="PNG")

    pdf = tmp_path / "report.pdf"
    out_dir = tmp_path / "analyse-output"
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
    assert "audit:" in result.stdout

    db = AuditDB.open_default()
    analyses = db.list_analyses()
    assert len(analyses) == 1

    entry = analyses[0]
    expected_sha = hashlib.sha256(tile.read_bytes()).hexdigest()
    assert entry.image_sha256 == expected_sha

    expected_name_hash = hashlib.sha256(b"tile.png").hexdigest()
    assert entry.filename_hash == expected_name_hash
