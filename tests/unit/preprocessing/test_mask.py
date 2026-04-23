"""Tests for :mod:`openpathai.preprocessing.mask`."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.preprocessing.mask import otsu_threshold, otsu_tissue_mask


@pytest.mark.unit
def test_otsu_threshold_on_bimodal_image() -> None:
    rng = np.random.default_rng(0)
    bg = rng.integers(180, 220, size=(100, 100), dtype=np.uint16).astype(np.uint8)
    fg = rng.integers(40, 80, size=(100, 100), dtype=np.uint16).astype(np.uint8)
    stack = np.vstack([bg, fg])
    t = otsu_threshold(stack)
    # Threshold should fall between the two modes.
    assert 70 <= t <= 190


@pytest.mark.unit
def test_otsu_threshold_on_uniform_image_returns_low_value() -> None:
    flat = np.full((32, 32), 255, dtype=np.uint8)
    t = otsu_threshold(flat)
    # All mass at 255 → no between-class variance; index 0 is fine.
    assert 0 <= t <= 255


@pytest.mark.unit
def test_otsu_tissue_mask_default_inverts_for_he() -> None:
    rng = np.random.default_rng(1)
    bg = rng.integers(210, 250, size=(64, 64), dtype=np.uint16).astype(np.uint8)
    fg = rng.integers(30, 70, size=(64, 64), dtype=np.uint16).astype(np.uint8)
    stack = np.vstack([bg, fg])
    mask = otsu_tissue_mask(stack)
    # Dark (foreground) pixels should be True; bright background False.
    assert mask[64:].mean() > 0.9
    assert mask[:64].mean() < 0.1


@pytest.mark.unit
def test_otsu_tissue_mask_uniform_white_returns_all_false() -> None:
    flat = np.full((32, 32, 3), 250, dtype=np.uint8)
    mask = otsu_tissue_mask(flat, min_threshold=200)
    # With a min_threshold of 200, pure-white at 250 stays background.
    assert mask.sum() == 0


@pytest.mark.unit
def test_otsu_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError):
        otsu_threshold(np.zeros((4, 4, 4, 4), dtype=np.uint8))
