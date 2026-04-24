"""Phase 13 — CLI surface for foundation + mil + linear-probe."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app
from tests.conftest import strip_ansi

runner = CliRunner(mix_stderr=False)


def test_foundation_list_shows_all_eight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    result = runner.invoke(app, ["foundation", "list"])
    assert result.exit_code == 0, result.stderr or result.stdout
    out = strip_ansi(result.stdout)
    for name in (
        "dinov2_vits14",
        "uni",
        "uni2_h",
        "conch",
        "virchow2",
        "prov_gigapath",
        "hibou",
        "ctranspath",
    ):
        assert name in out, f"{name!r} missing"


def test_foundation_resolve_uni_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    result = runner.invoke(app, ["foundation", "resolve", "uni"])
    assert result.exit_code == 0, result.stderr or result.stdout
    payload = json.loads(strip_ansi(result.stdout))
    assert payload["requested_id"] == "uni"
    assert payload["resolved_id"] == "dinov2_vits14"
    assert payload["reason"] == "hf_token_missing"


def test_foundation_resolve_unknown_exits_2() -> None:
    result = runner.invoke(app, ["foundation", "resolve", "no_such_model"])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "unknown" in combined


def test_foundation_resolve_strict_without_token_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    result = runner.invoke(app, ["foundation", "resolve", "uni", "--strict"])
    assert result.exit_code != 0


def test_mil_list_shows_all_five() -> None:
    result = runner.invoke(app, ["mil", "list"])
    assert result.exit_code == 0, result.stderr or result.stdout
    out = strip_ansi(result.stdout)
    for name in ("abmil", "clam_sb", "clam_mb", "transmil", "dsmil"):
        assert name in out


def test_linear_probe_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Extract, save, then fit via the CLI."""
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))
    # Build a synthetic separable 3-class bundle.
    rng = np.random.default_rng(0)
    anchors = rng.standard_normal((3, 8)) * 4.0
    feats = np.concatenate(
        [anchors[c] + 0.3 * rng.standard_normal((30, 8)) for c in range(3)]
    ).astype(np.float32)
    labels = np.concatenate([np.full(30, c) for c in range(3)]).astype(np.int64)
    bundle_path = tmp_path / "bundle.npz"
    np.savez(
        bundle_path,
        features_train=feats,
        labels_train=labels,
        class_names=np.array(["a", "b", "c"], dtype=object),
    )

    out = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "linear-probe",
            "--features",
            str(bundle_path),
            "--backbone",
            "uni",
            "--out",
            str(out),
            "--no-audit",
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["backbone_id"] == "uni"
    # UNI requested → falls back to DINOv2 in the report.
    assert payload["resolved_backbone_id"] == "dinov2_vits14"
    assert payload["fallback_reason"] == "hf_token_missing"
    assert payload["accuracy"] >= 0.9
    assert out.exists()


def test_linear_probe_missing_features_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "linear-probe",
            "--features",
            str(tmp_path / "never.npz"),
        ],
    )
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "not found" in combined
