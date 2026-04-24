"""Tissue-fold QC — elongated dark-edge streaks.

Folds manifest as dark lines (where tissue is stacked twice) and
produce a tail in the gradient-magnitude distribution. We compute a
Sobel-style gradient, threshold the top 1% of magnitudes, and count
the fraction of pixels that fall in that tail. A clean slide has
broadly-distributed gradients; a folded slide has concentrated
high-gradient tails.
"""

from __future__ import annotations

import numpy as np

from openpathai.preprocessing.qc.findings import QCFinding

__all__ = [
    "DEFAULT_FOLD_THRESHOLD",
    "fold_finding",
    "fold_fraction",
]


DEFAULT_FOLD_THRESHOLD: float = 0.05
"""Flag when top-gradient fraction x 100 exceeds this threshold."""


_SOBEL_X = np.array(
    [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]],
    dtype=np.float32,
)
_SOBEL_Y = _SOBEL_X.T


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.float32)
    if image.ndim == 3 and image.shape[2] >= 3:
        rgb = image[..., :3].astype(np.float32)
        return rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    raise ValueError(f"Unsupported image shape {image.shape} for folds QC")


def _conv3x3(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    pad = np.pad(image, 1, mode="edge")
    h, w = image.shape
    out = np.zeros_like(image, dtype=np.float32)
    for i in range(3):
        for j in range(3):
            out += kernel[i, j] * pad[i : i + h, j : j + w]
    return out


def _gradient_magnitude(image: np.ndarray) -> np.ndarray:
    gray = _to_grayscale(image)
    gx = _conv3x3(gray, _SOBEL_X)
    gy = _conv3x3(gray, _SOBEL_Y)
    return np.sqrt(gx * gx + gy * gy)


def fold_fraction(
    image: np.ndarray,
    *,
    percentile: float = 99.0,
    ratio: float = 0.5,
) -> float:
    """Fraction of pixels whose gradient is within ``ratio`` of the
    ``percentile``-th magnitude.

    The metric rewards "tails" — a spike of very high gradients — without
    over-weighting mean edge strength (which is similar on clean + folded
    slides).
    """
    mag = _gradient_magnitude(image)
    high = float(np.percentile(mag, percentile))
    if high <= 1e-6:
        return 0.0
    mask = mag >= (high * ratio)
    total = mask.size
    return float(np.count_nonzero(mask)) / float(total) if total else 0.0


def fold_finding(
    image: np.ndarray,
    *,
    threshold: float = DEFAULT_FOLD_THRESHOLD,
) -> QCFinding:
    fraction = fold_fraction(image)
    passed = fraction <= threshold
    severity = "info" if passed else "warn"
    if passed:
        message = f"Top-gradient fraction {fraction * 100:.2f}% ≤ threshold {threshold * 100:.2f}%."
    else:
        message = (
            f"Top-gradient fraction {fraction * 100:.2f}% > threshold "
            f"{threshold * 100:.2f}% — possible folds / streaks."
        )
    return QCFinding(
        check="folds",
        severity=severity,
        score=fraction,
        passed=passed,
        message=message,
    )
