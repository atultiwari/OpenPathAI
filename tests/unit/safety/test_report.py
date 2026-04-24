"""PDF report rendering — determinism, PHI leak guard, readability."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from openpathai.safety import AnalysisResult, BorderlineDecision, ClassProbability
from openpathai.safety.report import ReportRenderError, render_pdf

reportlab = pytest.importorskip("reportlab")


def _fixture_result(**overrides) -> AnalysisResult:
    defaults: dict = {
        "image_sha256": "a" * 64,
        "model_name": "resnet18",
        "explainer_name": "gradcam",
        "probabilities": (
            ClassProbability("normal", 0.12),
            ClassProbability("tumour", 0.78),
            ClassProbability("other", 0.10),
        ),
        "borderline": BorderlineDecision(
            predicted_class=1,
            confidence=0.78,
            decision="positive",
            band="high",
            low=0.4,
            high=0.7,
        ),
        "manifest_hash": "b" * 64,
        "image_caption": "smoke-test",
        "timestamp": datetime(2026, 4, 24, 12, 0, 0),
    }
    defaults.update(overrides)
    return AnalysisResult(**defaults)


def test_render_creates_non_empty_pdf(tmp_path: Path) -> None:
    out = tmp_path / "report.pdf"
    render_pdf(_fixture_result(), out)
    assert out.exists()
    assert out.stat().st_size > 512
    assert out.read_bytes().startswith(b"%PDF-")


def test_render_is_deterministic(tmp_path: Path) -> None:
    r = _fixture_result()
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    render_pdf(r, a)
    render_pdf(r, b)
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()


def test_render_changes_with_decision(tmp_path: Path) -> None:
    # Two different decisions must not produce identical bytes.
    positive = tmp_path / "p.pdf"
    negative_result = _fixture_result(
        borderline=BorderlineDecision(
            predicted_class=0,
            confidence=0.05,
            decision="negative",
            band="low",
            low=0.4,
            high=0.7,
        )
    )
    negative = tmp_path / "n.pdf"
    render_pdf(_fixture_result(), positive)
    render_pdf(negative_result, negative)
    assert positive.read_bytes() != negative.read_bytes()


def test_path_leak_guard_blocks_user_path(tmp_path: Path) -> None:
    r = _fixture_result(image_caption="tile from /Users/phi/case001.svs")
    with pytest.raises(ReportRenderError, match="filesystem path"):
        render_pdf(r, tmp_path / "leak.pdf")


def test_path_leak_guard_blocks_home_path(tmp_path: Path) -> None:
    r = _fixture_result(image_caption="/home/anyone/phi.png")
    with pytest.raises(ReportRenderError, match="filesystem path"):
        render_pdf(r, tmp_path / "leak.pdf")


def test_pdf_does_not_contain_path_prefixes(tmp_path: Path) -> None:
    # No Users/ or home/ ever survives into the output text stream.
    out = tmp_path / "clean.pdf"
    render_pdf(_fixture_result(), out)
    blob = out.read_bytes()
    assert b"/Users/" not in blob
    assert b"/home/" not in blob
