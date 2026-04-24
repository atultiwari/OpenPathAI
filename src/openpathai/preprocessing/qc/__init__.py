"""Quality-control helpers — Phase 9.

Pure-numpy checks that operate on an RGB thumbnail (or a tile) and
return a :class:`QCFinding`. The aggregator walks a cohort and
emits a :class:`CohortQCReport`; the renderer writes HTML + PDF.
"""

from __future__ import annotations

from openpathai.preprocessing.qc.aggregate import (
    CohortQCReport,
    SlideQCReport,
    run_all_checks,
)
from openpathai.preprocessing.qc.blur import (
    DEFAULT_BLUR_THRESHOLD,
    blur_finding,
    laplacian_variance,
)
from openpathai.preprocessing.qc.findings import QCFinding, QCSeverity
from openpathai.preprocessing.qc.focus import (
    DEFAULT_FOCUS_THRESHOLD,
    focus_finding,
    focus_score,
)
from openpathai.preprocessing.qc.folds import (
    DEFAULT_FOLD_THRESHOLD,
    fold_finding,
    fold_fraction,
)
from openpathai.preprocessing.qc.pen_marks import (
    DEFAULT_PEN_FRACTION_THRESHOLD,
    DEFAULT_PEN_SATURATION_THRESHOLD,
    pen_mark_finding,
    pen_mark_fraction,
)
from openpathai.preprocessing.qc.report import (
    QCReportRenderError,
    render_html,
    render_pdf,
)

__all__ = [
    "DEFAULT_BLUR_THRESHOLD",
    "DEFAULT_FOCUS_THRESHOLD",
    "DEFAULT_FOLD_THRESHOLD",
    "DEFAULT_PEN_FRACTION_THRESHOLD",
    "DEFAULT_PEN_SATURATION_THRESHOLD",
    "CohortQCReport",
    "QCFinding",
    "QCReportRenderError",
    "QCSeverity",
    "SlideQCReport",
    "blur_finding",
    "focus_finding",
    "focus_score",
    "fold_finding",
    "fold_fraction",
    "laplacian_variance",
    "pen_mark_finding",
    "pen_mark_fraction",
    "render_html",
    "render_pdf",
    "run_all_checks",
]
