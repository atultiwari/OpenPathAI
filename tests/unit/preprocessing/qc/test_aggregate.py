"""Aggregate QC — ``run_all_checks`` + ``CohortQCReport``."""

from __future__ import annotations

import numpy as np

from openpathai.preprocessing.qc import (
    CohortQCReport,
    QCFinding,
    SlideQCReport,
    run_all_checks,
)


def _clean() -> np.ndarray:
    return np.full((64, 64, 3), (210, 180, 200), dtype=np.uint8)


def _painted() -> np.ndarray:
    img = _clean()
    img[20:30, :, :] = [30, 30, 220]  # blue pen streak
    return img


def test_run_all_checks_returns_four_findings() -> None:
    findings = run_all_checks(_clean())
    assert len(findings) == 4
    checks = {f.check for f in findings}
    assert checks == {"blur", "pen_marks", "folds", "focus"}
    for f in findings:
        assert isinstance(f, QCFinding)


def test_slide_qc_report_severity_and_passed() -> None:
    findings = run_all_checks(_painted())
    report = SlideQCReport.from_findings("slide-1", findings)
    assert report.slide_id == "slide-1"
    assert report.passed is False
    assert report.severity in {"warn", "fail"}
    # Round-trip the typed findings back out.
    typed = report.qc_findings
    assert [f.check for f in typed] == ["blur", "pen_marks", "folds", "focus"]


def test_cohort_qc_report_summary_counts_pass_warn_fail() -> None:
    ok_slide = SlideQCReport.from_findings("ok", run_all_checks(_clean()))
    bad_slide = SlideQCReport.from_findings("bad", run_all_checks(_painted()))
    report = CohortQCReport(
        cohort_id="demo",
        slide_findings=(ok_slide, bad_slide),
    )
    summary = report.summary()
    assert summary["pass"] + summary["warn"] + summary["fail"] == 2
    assert summary["fail"] >= 1  # blue streak forces a failure


def test_cohort_qc_report_round_trips_through_model_dump() -> None:
    slide = SlideQCReport.from_findings("ok", run_all_checks(_clean()))
    report = CohortQCReport(cohort_id="demo", slide_findings=(slide,))
    payload = report.model_dump(mode="json")
    reloaded = CohortQCReport.model_validate(payload)
    assert reloaded.cohort_id == report.cohort_id
    assert len(reloaded.slide_findings) == 1
    assert reloaded.slide_findings[0].slide_id == "ok"


def test_slide_ids_property() -> None:
    report = CohortQCReport(
        cohort_id="demo",
        slide_findings=(
            SlideQCReport.from_findings("a", run_all_checks(_clean())),
            SlideQCReport.from_findings("b", run_all_checks(_clean())),
        ),
    )
    assert report.slide_ids == ("a", "b")
