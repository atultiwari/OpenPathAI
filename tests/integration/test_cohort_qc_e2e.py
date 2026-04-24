"""End-to-end cohort QC with 20 synthetic slides (master-plan acceptance)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from openpathai.io import Cohort, SlideRef
from openpathai.preprocessing.qc import render_html, render_pdf

reportlab = pytest.importorskip("reportlab")


def _deterministic_thumbnail(slide_id: str) -> np.ndarray:
    """Per-slide thumbnail whose QC outcome depends on the slide id."""
    rng = np.random.default_rng(int(hashlib.sha256(slide_id.encode()).hexdigest()[:8], 16))
    base = np.full((128, 128, 3), (210, 180, 200), dtype=np.uint8)
    # Half the slides get a blue streak → QC flag.
    if rng.random() < 0.5:
        base[40:60, :, :] = [30, 30, 220]
    return base


def test_twenty_slide_cohort_end_to_end(tmp_path: Path) -> None:
    slides = tuple(
        SlideRef(slide_id=f"slide-{i:02d}", path=f"/tmp/slide-{i:02d}.svs") for i in range(20)
    )
    cohort = Cohort(id="twenty", slides=slides)

    report = cohort.run_qc(lambda slide: _deterministic_thumbnail(slide.slide_id))
    summary = report.summary()
    # Exactly 20 slides processed.
    assert sum(summary.values()) == 20
    # The deterministic thumbnail distribution guarantees at least one
    # flagged slide across 20 runs.
    assert summary["fail"] >= 1

    html = render_html(report, tmp_path / "report.html")
    assert html.is_file()
    assert "twenty" in html.read_text(encoding="utf-8")

    pdf = render_pdf(report, tmp_path / "report.pdf")
    assert pdf.is_file()
    assert pdf.read_bytes().startswith(b"%PDF-")
