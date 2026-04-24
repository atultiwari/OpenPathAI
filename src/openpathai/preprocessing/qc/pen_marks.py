"""Pen-mark QC check — HSV heuristic for highly-saturated ink hues.

H&E tissue has a predictable hue distribution (pink/purple). Marker
ink is highly-saturated blue/green/red. We flag a slide when the
fraction of pixels with saturation ≥ ``sat_threshold`` **and** a hue
inside the "ink" bands exceeds ``fraction_threshold``.

Pure numpy. Operates on an RGB thumbnail (or tile).
"""

from __future__ import annotations

import numpy as np

from openpathai.preprocessing.qc.findings import QCFinding

__all__ = [
    "DEFAULT_PEN_FRACTION_THRESHOLD",
    "DEFAULT_PEN_SATURATION_THRESHOLD",
    "pen_mark_finding",
    "pen_mark_fraction",
]


DEFAULT_PEN_FRACTION_THRESHOLD: float = 0.02
"""Flag the slide when > 2% of pixels look like ink."""

DEFAULT_PEN_SATURATION_THRESHOLD: float = 0.4
"""HSV saturation above which a pixel is "highly saturated"."""


# Hue bands where pathology pen marks typically sit. Values in
# [0.0, 1.0); match ``colorsys.rgb_to_hsv`` conventions (red=0,
# green~0.33, blue~0.66). Red wraps at the ends of the interval
# ((220, 30, 40) sits at ~0.99) so we include both wrap-around
# bands. H&E hues sit around 0.75-0.92 (pink/purple); the blue band
# stops at 0.72 so we don't flag H&E itself.
_INK_HUE_BANDS: tuple[tuple[float, float], ...] = (
    (0.00, 0.05),  # red (low end)
    (0.95, 1.00),  # red (wraparound)
    (0.28, 0.45),  # green
    (0.55, 0.72),  # blue
)


def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """Vectorised RGB → HSV. Input ``(H, W, 3)`` uint8; output float32."""
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError(f"pen_marks expects (H, W, 3) RGB, got {rgb.shape}")
    r = rgb[..., 0].astype(np.float32) / 255.0
    g = rgb[..., 1].astype(np.float32) / 255.0
    b = rgb[..., 2].astype(np.float32) / 255.0
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    v = maxc
    delta = maxc - minc
    s = np.where(maxc > 0, delta / (maxc + 1e-12), 0.0)
    # Hue — vectorised from the scalar algorithm.
    h = np.zeros_like(maxc, dtype=np.float32)
    mask = delta > 1e-8
    rc = np.where(mask, (maxc - r) / (delta + 1e-12), 0.0)
    gc = np.where(mask, (maxc - g) / (delta + 1e-12), 0.0)
    bc = np.where(mask, (maxc - b) / (delta + 1e-12), 0.0)
    h = np.where(r == maxc, bc - gc, h)
    h = np.where(g == maxc, 2.0 + rc - bc, h)
    h = np.where(b == maxc, 4.0 + gc - rc, h)
    h = (h / 6.0) % 1.0
    h = np.where(mask, h, 0.0)
    return np.stack([h, s, v], axis=-1)


def _in_ink_bands(hue: np.ndarray) -> np.ndarray:
    out = np.zeros_like(hue, dtype=bool)
    for low, high in _INK_HUE_BANDS:
        out |= (hue >= low) & (hue <= high)
    return out


def pen_mark_fraction(
    image: np.ndarray,
    *,
    sat_threshold: float = DEFAULT_PEN_SATURATION_THRESHOLD,
) -> float:
    """Fraction of pixels in ``image`` that look like pen marks."""
    hsv = _rgb_to_hsv(image)
    hue = hsv[..., 0]
    sat = hsv[..., 1]
    mask = _in_ink_bands(hue) & (sat >= sat_threshold)
    total = mask.size
    if total == 0:
        return 0.0
    return float(np.count_nonzero(mask)) / float(total)


def pen_mark_finding(
    image: np.ndarray,
    *,
    threshold: float = DEFAULT_PEN_FRACTION_THRESHOLD,
    sat_threshold: float = DEFAULT_PEN_SATURATION_THRESHOLD,
) -> QCFinding:
    """Run the pen-mark check on ``image``."""
    fraction = pen_mark_fraction(image, sat_threshold=sat_threshold)
    passed = fraction <= threshold
    severity = "info" if passed else "fail"
    if passed:
        message = f"Pen-mark coverage {fraction * 100:.2f}% ≤ threshold {threshold * 100:.2f}%."
    else:
        message = (
            f"Pen-mark coverage {fraction * 100:.2f}% > threshold "
            f"{threshold * 100:.2f}% — ink suspected."
        )
    return QCFinding(
        check="pen_marks",
        severity=severity,
        score=fraction,
        passed=passed,
        message=message,
    )
