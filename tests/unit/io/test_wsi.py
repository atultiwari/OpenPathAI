"""Tests for :mod:`openpathai.io.wsi` (PillowSlideReader fallback path)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from openpathai.io.wsi import (
    PillowSlideReader,
    SlideBackend,
    open_slide,
)


@pytest.mark.unit
def test_pillow_reader_reports_dimensions(synthetic_slide_path: Path) -> None:
    with PillowSlideReader(synthetic_slide_path, mpp=0.5) as reader:
        info = reader.info
        assert info.width == 1024
        assert info.height == 1024
        assert info.mpp == pytest.approx(0.5)
        assert info.level_count == 1
        assert info.level_dimensions == ((1024, 1024),)
        assert info.backend is SlideBackend.PILLOW


@pytest.mark.unit
def test_pillow_reader_read_region_shape_and_dtype(synthetic_slide_path: Path) -> None:
    with PillowSlideReader(synthetic_slide_path) as reader:
        tile = reader.read_region(location=(100, 100), size=(128, 128))
    assert tile.shape == (128, 128, 3)
    assert tile.dtype == np.uint8


@pytest.mark.unit
def test_pillow_reader_rejects_nonzero_level(synthetic_slide_path: Path) -> None:
    with PillowSlideReader(synthetic_slide_path) as reader, pytest.raises(ValueError):
        reader.read_region((0, 0), (10, 10), level=1)


@pytest.mark.unit
def test_open_slide_auto_falls_back_to_pillow(synthetic_slide_path: Path) -> None:
    reader = open_slide(synthetic_slide_path, mpp=0.5)
    try:
        # Auto-pick should pick Pillow on plain TIFFs (openslide may or
        # may not be installed; but even if it is, `OpenSlideReader`
        # will likely fail on this flat TIFF and fall through).
        assert reader.info.width == 1024
        assert reader.info.mpp == pytest.approx(0.5)
    finally:
        reader.close()


@pytest.mark.unit
def test_open_slide_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        open_slide(tmp_path / "nope.tiff")


@pytest.mark.unit
def test_open_slide_prefer_pillow(synthetic_slide_path: Path) -> None:
    reader = open_slide(synthetic_slide_path, prefer=SlideBackend.PILLOW, mpp=0.7)
    try:
        assert reader.info.backend is SlideBackend.PILLOW
        assert reader.info.mpp == pytest.approx(0.7)
    finally:
        reader.close()
