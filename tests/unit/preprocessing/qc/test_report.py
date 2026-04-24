"""HTML + PDF cohort QC report."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from openpathai.preprocessing.qc import (
    CohortQCReport,
    SlideQCReport,
    render_html,
    run_all_checks,
)
from openpathai.preprocessing.qc.report import QCReportRenderError, render_pdf

reportlab = pytest.importorskip("reportlab")


def _clean() -> np.ndarray:
    return np.full((64, 64, 3), (210, 180, 200), dtype=np.uint8)


def _report(cohort_id: str = "demo") -> CohortQCReport:
    slides = tuple(
        SlideQCReport.from_findings(f"slide-{i}", run_all_checks(_clean())) for i in range(3)
    )
    return CohortQCReport(
        cohort_id=cohort_id,
        generated_at_utc="2026-04-24T12:00:00+00:00",
        slide_findings=slides,
    )


def test_html_contains_every_slide_id(tmp_path: Path) -> None:
    report = _report()
    out = render_html(report, tmp_path / "q.html")
    text = out.read_text(encoding="utf-8")
    for slide in report.slide_findings:
        assert slide.slide_id in text
    # Self-contained — no external <link> / <script>.
    assert "<link" not in text
    assert "<script" not in text


def test_html_is_deterministic(tmp_path: Path) -> None:
    report = _report()
    a = render_html(report, tmp_path / "a.html").read_bytes()
    b = render_html(report, tmp_path / "b.html").read_bytes()
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()


def test_pdf_non_empty_and_deterministic(tmp_path: Path) -> None:
    report = _report()
    a = render_pdf(report, tmp_path / "a.pdf")
    b = render_pdf(report, tmp_path / "b.pdf")
    assert a.read_bytes().startswith(b"%PDF-")
    assert a.stat().st_size > 256
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()


def test_pdf_changes_when_report_changes(tmp_path: Path) -> None:
    a_report = _report(cohort_id="demo-a")
    b_report = _report(cohort_id="demo-b")
    a = render_pdf(a_report, tmp_path / "a.pdf").read_bytes()
    b = render_pdf(b_report, tmp_path / "b.pdf").read_bytes()
    assert a != b


def test_render_pdf_raises_without_reportlab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Force the reportlab find_spec to return None and assert failure."""
    import openpathai.preprocessing.qc.report as report_module

    def _fake_find_spec(name: str) -> None:
        return None

    monkeypatch.setattr(report_module.importlib_util, "find_spec", _fake_find_spec)
    with pytest.raises(QCReportRenderError, match="ReportLab"):
        render_pdf(_report(), tmp_path / "bad.pdf")
