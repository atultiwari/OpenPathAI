"""Cohort-scope aggregation of per-slide QC findings."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from openpathai.preprocessing.qc.blur import blur_finding
from openpathai.preprocessing.qc.findings import QCFinding
from openpathai.preprocessing.qc.focus import focus_finding
from openpathai.preprocessing.qc.folds import fold_finding
from openpathai.preprocessing.qc.pen_marks import pen_mark_finding

__all__ = [
    "CohortQCReport",
    "SlideQCReport",
    "run_all_checks",
]


def run_all_checks(image: np.ndarray) -> tuple[QCFinding, ...]:
    """Run every Phase-9 QC helper on ``image``.

    Order matches the spec: blur → pen_marks → folds → focus. Callers
    that need custom ordering or thresholds should call the helpers
    directly.
    """
    return (
        blur_finding(image),
        pen_mark_finding(image),
        fold_finding(image),
        focus_finding(image),
    )


def _utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class SlideQCReport(BaseModel):
    """Per-slide QC rollup — a list of :class:`QCFinding` findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slide_id: str = Field(min_length=1)
    findings: tuple[dict, ...]
    """Findings are serialised as plain dicts so the pydantic model is
    round-trippable. Use :attr:`qc_findings` when you want typed
    objects back."""

    @property
    def qc_findings(self) -> tuple[QCFinding, ...]:
        return tuple(QCFinding(**f) for f in self.findings)

    @property
    def passed(self) -> bool:
        """True when every finding on this slide passed."""
        return all(f["passed"] for f in self.findings)

    @property
    def severity(self) -> str:
        """Most-severe severity level observed."""
        rank = {"info": 0, "warn": 1, "fail": 2}
        worst = max((rank[f["severity"]] for f in self.findings), default=0)
        inverse = {0: "info", 1: "warn", 2: "fail"}
        return inverse[worst]

    @classmethod
    def from_findings(
        cls,
        slide_id: str,
        findings: tuple[QCFinding, ...],
    ) -> SlideQCReport:
        return cls(
            slide_id=slide_id,
            findings=tuple(
                {
                    "check": f.check,
                    "severity": f.severity,
                    "score": float(f.score),
                    "passed": bool(f.passed),
                    "message": f.message,
                }
                for f in findings
            ),
        )


class CohortQCReport(BaseModel):
    """Cohort-scope QC rollup. Round-trippable + JSON-dumpable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort_id: str = Field(min_length=1)
    generated_at_utc: str = Field(default_factory=_utcnow_iso)
    slide_findings: tuple[SlideQCReport, ...]

    def summary(self) -> dict[str, int]:
        """Counts of (pass, warn, fail) across every slide."""
        counts = {"pass": 0, "warn": 0, "fail": 0}
        for slide in self.slide_findings:
            if slide.passed:
                counts["pass"] += 1
            elif slide.severity == "fail":
                counts["fail"] += 1
            else:
                counts["warn"] += 1
        return counts

    @property
    def slide_ids(self) -> tuple[str, ...]:
        return tuple(slide.slide_id for slide in self.slide_findings)
