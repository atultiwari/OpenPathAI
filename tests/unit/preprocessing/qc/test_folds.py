"""Fold / streak QC."""

from __future__ import annotations

import numpy as np

from openpathai.preprocessing.qc import fold_finding
from openpathai.preprocessing.qc.folds import fold_fraction


def _flat() -> np.ndarray:
    return np.full((96, 96, 3), 200, dtype=np.uint8)


def test_flat_image_passes() -> None:
    finding = fold_finding(_flat())
    assert finding.passed is True
    assert finding.check == "folds"


def test_custom_threshold_forces_fail() -> None:
    img = _flat()
    img[:, 48, :] = 30  # single dark vertical line
    finding = fold_finding(img, threshold=0.0)
    assert finding.passed is False


def test_fold_fraction_nonzero_on_streak() -> None:
    img = _flat()
    img[:, 48, :] = 30
    assert fold_fraction(img) > 0.0


def test_fold_fraction_zero_on_constant() -> None:
    assert fold_fraction(_flat()) == 0.0
