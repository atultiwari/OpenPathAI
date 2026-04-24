"""QC finding types — the shape every QC check returns.

Kept deliberately tiny + pure so every QC helper can land + be
tested in isolation. The aggregator in
:mod:`openpathai.preprocessing.qc.aggregate` wraps these rows into a
``CohortQCReport``; the renderer in :mod:`.report` serialises that to
HTML / PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "QCFinding",
    "QCSeverity",
]


QCSeverity = Literal["info", "warn", "fail"]
"""Severity ladder: ``fail`` is disqualifying, ``warn`` is cautionary,
``info`` is a noted observation (passed but worth surfacing)."""


@dataclass(frozen=True, slots=True)
class QCFinding:
    """Outcome of one quality-control check on one image.

    Attributes
    ----------
    check:
        Stable id — ``"blur"`` / ``"pen_marks"`` / ``"folds"`` /
        ``"focus"`` in Phase 9.
    severity:
        Routing outcome. ``fail`` is disqualifying.
    score:
        The raw score that drove the decision (higher = better for
        blur/focus; lower = better for pen_marks/folds).
    passed:
        ``True`` when the check considered the image acceptable.
    message:
        Human-readable explanation — shown verbatim in the HTML / PDF
        report.
    """

    check: str
    severity: QCSeverity
    score: float
    passed: bool
    message: str

    @property
    def badge(self) -> str:
        """Short emoji badge for console / HTML."""
        if not self.passed:
            return "🔴" if self.severity == "fail" else "🟠"
        if self.severity == "info":
            return "🔵"
        return "🟢"
