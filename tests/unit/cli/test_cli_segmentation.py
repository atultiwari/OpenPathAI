"""Phase 14 — ``openpathai segmentation`` CLI surface."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner(mix_stderr=False)


def test_list_shows_closed_and_promptable() -> None:
    result = runner.invoke(app, ["segmentation", "list"])
    assert result.exit_code == 0, result.stderr or result.stdout
    out = strip_ansi(result.stdout)
    # Closed-vocab.
    for name in ("tiny_unet", "attention_unet", "nnunet_v2", "segformer", "hover_net"):
        assert name in out
    # Promptable.
    for name in ("sam2", "medsam", "medsam2", "medsam3", "synthetic_click"):
        assert name in out


def test_resolve_tiny_unet_open() -> None:
    result = runner.invoke(app, ["segmentation", "resolve", "tiny_unet"])
    assert result.exit_code == 0
    payload = json.loads(strip_ansi(result.stdout))
    assert payload["resolved_id"] == "tiny_unet"
    assert payload["reason"] == "ok"


def test_resolve_medsam2_falls_back_to_synthetic_click() -> None:
    result = runner.invoke(app, ["segmentation", "resolve", "medsam2"])
    assert result.exit_code == 0
    payload = json.loads(strip_ansi(result.stdout))
    assert payload["resolved_id"] == "synthetic_click"


def test_resolve_nnunet_falls_back_to_synthetic_tissue() -> None:
    result = runner.invoke(app, ["segmentation", "resolve", "nnunet_v2"])
    assert result.exit_code == 0
    payload = json.loads(strip_ansi(result.stdout))
    assert payload["resolved_id"] == "synthetic_tissue"


def test_resolve_unknown_exits_2() -> None:
    result = runner.invoke(app, ["segmentation", "resolve", "no_such"])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "unknown" in combined
