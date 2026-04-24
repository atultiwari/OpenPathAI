"""``openpathai nl`` CLI — classify, segment, draft."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner(mix_stderr=False)


def _write_tile(path: Path, size: int = 64, seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    arr = (rng.random((size, size, 3)) * 255).astype(np.uint8)
    Image.fromarray(arr).save(path)


def test_nl_help_exits_0() -> None:
    result = runner.invoke(app, ["nl", "--help"])
    assert result.exit_code == 0
    out = strip_ansi(result.stdout)
    for token in ("classify", "segment", "draft"):
        assert token in out


def test_nl_classify_round_trip(tmp_path: Path) -> None:
    tile = tmp_path / "tile.png"
    _write_tile(tile)
    result = runner.invoke(
        app,
        [
            "nl",
            "classify",
            str(tile),
            "--prompt",
            "tumor",
            "--prompt",
            "normal",
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["prompts"] == ["tumor", "normal"]
    assert abs(sum(payload["probs"]) - 1.0) < 1e-6
    assert payload["resolved_backbone_id"] == "synthetic_text_encoder"


def test_nl_classify_needs_two_prompts(tmp_path: Path) -> None:
    tile = tmp_path / "tile.png"
    _write_tile(tile)
    result = runner.invoke(
        app,
        ["nl", "classify", str(tile), "--prompt", "tumor"],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "two --prompt" in combined


def test_nl_classify_missing_image_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "nl",
            "classify",
            str(tmp_path / "no-such.png"),
            "--prompt",
            "a",
            "--prompt",
            "b",
        ],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "image not found" in combined


def test_nl_segment_writes_mask_png(tmp_path: Path) -> None:
    tile = tmp_path / "tile.png"
    _write_tile(tile)
    out_png = tmp_path / "mask.png"
    result = runner.invoke(
        app,
        [
            "nl",
            "segment",
            str(tile),
            "--prompt",
            "gland",
            "--out",
            str(out_png),
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["resolved_model_id"] == "synthetic_click"
    assert payload["mask_shape"] == [64, 64]
    assert out_png.exists()
    with Image.open(out_png) as img:
        assert img.size == (64, 64)


def test_nl_segment_rejects_empty_prompt(tmp_path: Path) -> None:
    tile = tmp_path / "tile.png"
    _write_tile(tile)
    result = runner.invoke(
        app,
        ["nl", "segment", str(tile), "--prompt", " "],
    )
    assert result.exit_code == 2


def test_nl_draft_without_backend_exits_3() -> None:
    """CI cells don't have Ollama / LM Studio → exit 3 +
    actionable install message."""
    result = runner.invoke(
        app,
        ["nl", "draft", "fine-tune resnet18 on lc25000"],
    )
    assert result.exit_code == 3
    combined = result.stdout + (result.stderr or "")
    assert "No LLM backend" in combined or "No backend is reachable" in combined
