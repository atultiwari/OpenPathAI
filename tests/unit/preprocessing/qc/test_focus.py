"""Focus QC — Sobel-magnitude mean."""

from __future__ import annotations

import numpy as np

from openpathai.preprocessing.qc import focus_finding
from openpathai.preprocessing.qc.focus import focus_score


def _checkerboard(h: int = 64, w: int = 64, cell: int = 8) -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(0, h, cell):
        for j in range(0, w, cell):
            if ((i // cell) + (j // cell)) % 2:
                img[i : i + cell, j : j + cell] = 255
    return img


def test_sharp_checkerboard_passes_focus() -> None:
    finding = focus_finding(_checkerboard())
    assert finding.passed is True
    assert finding.check == "focus"
    assert finding.score > 10.0  # well above default threshold (2.0)


def test_flat_image_fails_focus() -> None:
    flat = np.full((64, 64, 3), 200, dtype=np.uint8)
    finding = focus_finding(flat)
    assert finding.passed is False
    assert finding.severity == "warn"


def test_focus_score_monotonic() -> None:
    sharp = _checkerboard(cell=4)
    dull = _checkerboard(cell=32)
    assert focus_score(sharp) > focus_score(dull)
