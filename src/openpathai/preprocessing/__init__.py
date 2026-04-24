"""Preprocessing primitives: stain normalisation and tissue masking.

These are the first data-layer operations pathology pipelines lean on:

* :class:`~openpathai.preprocessing.stain.MacenkoNormalizer` — Macenko
  stain normalisation (Macenko et al., 2009) in pure numpy, no external
  stain libraries required.
* :func:`~openpathai.preprocessing.mask.otsu_tissue_mask` — Otsu-
  thresholded tissue mask from a thumbnail or tile.
"""

from __future__ import annotations

from openpathai.preprocessing.mask import otsu_threshold, otsu_tissue_mask
from openpathai.preprocessing.qc import (
    CohortQCReport,
    QCFinding,
    QCReportRenderError,
    QCSeverity,
    SlideQCReport,
    blur_finding,
    focus_finding,
    fold_finding,
    pen_mark_finding,
    render_html,
    render_pdf,
    run_all_checks,
)
from openpathai.preprocessing.stain import MacenkoNormalizer, MacenkoStainMatrix

__all__ = [
    "CohortQCReport",
    "MacenkoNormalizer",
    "MacenkoStainMatrix",
    "QCFinding",
    "QCReportRenderError",
    "QCSeverity",
    "SlideQCReport",
    "blur_finding",
    "focus_finding",
    "fold_finding",
    "otsu_threshold",
    "otsu_tissue_mask",
    "pen_mark_finding",
    "render_html",
    "render_pdf",
    "run_all_checks",
]
