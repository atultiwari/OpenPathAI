"""Focus QC — Tenengrad-style Sobel-magnitude score.

Sharper images have more total edge energy. We normalise by image size
so the score is comparable across thumbnails at different resolutions.
Complementary to the blur check (variance of Laplacian) — both agree
on sharpness but they surface different failure modes: ``blur``
catches motion/shake blur, ``focus`` catches systemic lens defocus.
"""

from __future__ import annotations

import numpy as np

from openpathai.preprocessing.qc.findings import QCFinding
from openpathai.preprocessing.qc.folds import _gradient_magnitude

__all__ = [
    "DEFAULT_FOCUS_THRESHOLD",
    "focus_finding",
    "focus_score",
]


DEFAULT_FOCUS_THRESHOLD: float = 2.0
"""Score below this is flagged as out-of-focus.

The score is the mean gradient magnitude (after BT.601 luminance) —
units are 8-bit grayscale. Sharp thumbnails typically sit in
``[4, 20]``; flat / defocused ones drop below ``2``.
"""


def focus_score(image: np.ndarray) -> float:
    """Return a normalised sharpness score for ``image``."""
    mag = _gradient_magnitude(image)
    if mag.size == 0:
        return 0.0
    return float(np.mean(mag))


def focus_finding(
    image: np.ndarray,
    *,
    threshold: float = DEFAULT_FOCUS_THRESHOLD,
) -> QCFinding:
    score = focus_score(image)
    passed = score >= threshold
    severity = "info" if passed else "warn"
    if passed:
        message = f"Mean gradient magnitude {score:.2f} ≥ threshold {threshold:.2f}."
    else:
        message = (
            f"Mean gradient magnitude {score:.2f} < threshold {threshold:.2f} "
            f"— image appears out of focus."
        )
    return QCFinding(
        check="focus",
        severity=severity,
        score=score,
        passed=passed,
        message=message,
    )
