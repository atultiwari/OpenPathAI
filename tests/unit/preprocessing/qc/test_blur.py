"""Blur QC — variance of Laplacian."""

from __future__ import annotations

import numpy as np

from openpathai.preprocessing.qc import (
    DEFAULT_BLUR_THRESHOLD,
    blur_finding,
    laplacian_variance,
)


def _checkerboard(h: int = 64, w: int = 64, cell: int = 8) -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(0, h, cell):
        for j in range(0, w, cell):
            if ((i // cell) + (j // cell)) % 2:
                img[i : i + cell, j : j + cell] = 255
    return img


def test_sharp_checkerboard_passes_blur() -> None:
    finding = blur_finding(_checkerboard())
    assert finding.passed is True
    assert finding.check == "blur"
    assert finding.score > DEFAULT_BLUR_THRESHOLD


def test_flat_image_fails_blur() -> None:
    flat = np.full((64, 64, 3), 200, dtype=np.uint8)
    finding = blur_finding(flat)
    assert finding.passed is False
    assert finding.severity == "fail"
    # Edge-padded Laplacian of a constant image must be exactly zero.
    assert finding.score == 0.0


def test_custom_threshold_routes_pass() -> None:
    flat = np.full((64, 64, 3), 200, dtype=np.uint8)
    # With threshold 0.0 even a flat image passes.
    finding = blur_finding(flat, threshold=0.0)
    assert finding.passed is True


def test_laplacian_variance_monotonic() -> None:
    sharp = _checkerboard(cell=4)
    dull = _checkerboard(cell=32)
    assert laplacian_variance(sharp) > laplacian_variance(dull)


def test_grayscale_input_accepted() -> None:
    gray = np.random.default_rng(0).integers(0, 255, (32, 32), dtype=np.uint8)
    finding = blur_finding(gray, threshold=0.0)
    assert finding.check == "blur"
