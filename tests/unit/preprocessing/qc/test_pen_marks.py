"""Pen-marks QC."""

from __future__ import annotations

import numpy as np

from openpathai.preprocessing.qc import pen_mark_finding
from openpathai.preprocessing.qc.pen_marks import pen_mark_fraction


def _clean_he_thumbnail() -> np.ndarray:
    """Approximation of H&E — pinkish / purplish, low saturation."""
    img = np.full((64, 64, 3), (210, 180, 200), dtype=np.uint8)
    return img


def test_clean_thumbnail_passes() -> None:
    finding = pen_mark_finding(_clean_he_thumbnail())
    assert finding.passed is True
    assert finding.check == "pen_marks"


def test_blue_ink_streak_fails() -> None:
    img = _clean_he_thumbnail()
    # Saturated blue streak → in an ink hue band + high saturation.
    img[20:30, :, :] = [20, 30, 220]
    finding = pen_mark_finding(img)
    assert finding.passed is False
    assert finding.severity == "fail"
    assert finding.score > 0.0


def test_green_ink_streak_fails() -> None:
    img = _clean_he_thumbnail()
    img[:, 20:30, :] = [30, 210, 60]
    finding = pen_mark_finding(img)
    assert finding.passed is False


def test_red_ink_streak_fails() -> None:
    img = _clean_he_thumbnail()
    img[40:50, 10:55, :] = [220, 30, 40]
    finding = pen_mark_finding(img)
    assert finding.passed is False


def test_pen_mark_fraction_scales_with_streak_size() -> None:
    base = _clean_he_thumbnail()
    small = base.copy()
    small[30:32, :, :] = [30, 30, 220]
    big = base.copy()
    big[20:50, :, :] = [30, 30, 220]
    assert pen_mark_fraction(big) > pen_mark_fraction(small)


def test_custom_threshold() -> None:
    img = _clean_he_thumbnail()
    img[30:35, :, :] = [30, 30, 220]
    # With a very high threshold the same image should pass.
    finding = pen_mark_finding(img, threshold=0.99)
    assert finding.passed is True
