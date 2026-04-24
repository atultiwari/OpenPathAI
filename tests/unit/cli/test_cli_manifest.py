"""``openpathai manifest sign | verify`` CLI surface."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner(mix_stderr=False)


def _write_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "run_id": "run-abc",
                "graph_hash": "deadbeef",
                "datasets": ["lc25000"],
                "models": ["resnet18"],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_manifest_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["manifest", "--help"])
    assert result.exit_code == 0
    out = strip_ansi(result.stdout)
    for token in ("sign", "verify"):
        assert token in out


def test_sign_then_verify_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))
    manifest = _write_manifest(tmp_path)

    sign_result = runner.invoke(app, ["manifest", "sign", str(manifest)])
    assert sign_result.exit_code == 0, sign_result.stderr or sign_result.stdout
    payload = json.loads(sign_result.stdout)
    sig_path = Path(payload["signature_path"])
    assert sig_path.exists()

    verify_result = runner.invoke(app, ["manifest", "verify", str(manifest)])
    assert verify_result.exit_code == 0
    verified = json.loads(verify_result.stdout)
    assert verified["signature_ok"] is True


def test_verify_fails_on_tampered_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))
    manifest = _write_manifest(tmp_path)
    runner.invoke(app, ["manifest", "sign", str(manifest)])

    # Tamper.
    manifest.write_text(
        json.dumps(
            {
                "run_id": "run-abc",
                "graph_hash": "deadbeef",
                "datasets": ["LEAKED-OTHER-DATASET"],
                "models": ["resnet18"],
            }
        ),
        encoding="utf-8",
    )
    verify_result = runner.invoke(app, ["manifest", "verify", str(manifest)])
    assert verify_result.exit_code == 2
    payload = json.loads(verify_result.stdout)
    assert payload["signature_ok"] is False


def test_verify_missing_signature_exits_2(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    result = runner.invoke(app, ["manifest", "verify", str(manifest)])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "signature not found" in combined


def test_sign_missing_manifest_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["manifest", "sign", str(tmp_path / "nope.json")])
    assert result.exit_code == 2


def test_sign_malformed_manifest_exits_2(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    result = runner.invoke(app, ["manifest", "sign", str(bad)])
    assert result.exit_code == 2
