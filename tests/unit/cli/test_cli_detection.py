"""Phase 14 — ``openpathai detection`` CLI surface."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner(mix_stderr=False)


def test_list_shows_all_five() -> None:
    result = runner.invoke(app, ["detection", "list"])
    assert result.exit_code == 0, result.stderr or result.stdout
    out = strip_ansi(result.stdout)
    for name in ("yolov8", "yolov11", "yolov26", "rt_detr_v2", "synthetic_blob"):
        assert name in out


def test_resolve_open_adapter() -> None:
    result = runner.invoke(app, ["detection", "resolve", "synthetic_blob"])
    assert result.exit_code == 0
    payload = json.loads(strip_ansi(result.stdout))
    assert payload["resolved_id"] == "synthetic_blob"
    assert payload["reason"] == "ok"


def test_resolve_gated_stub_falls_back() -> None:
    result = runner.invoke(app, ["detection", "resolve", "yolov26"])
    assert result.exit_code == 0
    payload = json.loads(strip_ansi(result.stdout))
    assert payload["resolved_id"] == "synthetic_blob"
    assert payload["reason"] == "hf_gated"


def test_resolve_unknown_exits_2() -> None:
    result = runner.invoke(app, ["detection", "resolve", "no_such"])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "unknown" in combined


def test_resolve_strict_fails() -> None:
    result = runner.invoke(app, ["detection", "resolve", "yolov26", "--strict"])
    assert result.exit_code != 0
