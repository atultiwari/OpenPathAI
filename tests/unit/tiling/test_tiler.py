"""Tests for :mod:`openpathai.tiling.tiler`."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from openpathai.io.wsi import open_slide
from openpathai.tiling.tiler import GridTiler


@pytest.mark.unit
def test_grid_tiler_covers_full_slide_when_evenly_divisible(
    synthetic_slide_path: Path,
) -> None:
    reader = open_slide(synthetic_slide_path, mpp=0.5)
    try:
        tiler = GridTiler(tile_size_px=(256, 256))
        grid = tiler.plan(reader.info)
    finally:
        reader.close()
    # 1024 / 256 = 4 along each axis → 16 tiles.
    assert grid.n_tiles == 16
    assert grid.slide_width == 1024
    assert grid.slide_height == 1024
    assert grid.tile_size_px == (256, 256)


@pytest.mark.unit
def test_grid_tiler_honours_overlap(synthetic_slide_path: Path) -> None:
    reader = open_slide(synthetic_slide_path, mpp=0.5)
    try:
        tiler = GridTiler(tile_size_px=(256, 256), overlap_px=(128, 128))
        grid = tiler.plan(reader.info)
    finally:
        reader.close()
    # Stride = 128. Steps per axis = ceil((1024 - 256) / 128) + 1 = 7.
    assert grid.stride_px == (128, 128)
    assert grid.n_tiles == 7 * 7


@pytest.mark.unit
def test_grid_tiler_mpp_scaling(synthetic_slide_path: Path) -> None:
    # Slide MPP = 0.5. Target MPP = 1.0 -> each target tile covers 2x
    # the slide pixels.
    reader = open_slide(synthetic_slide_path, mpp=0.5)
    try:
        tiler = GridTiler(tile_size_px=(256, 256), target_mpp=1.0)
        grid = tiler.plan(reader.info)
    finally:
        reader.close()
    assert grid.tile_size_px == (512, 512)
    # 1024 / 512 = 2 tiles per axis → 4 total.
    assert grid.n_tiles == 4


@pytest.mark.unit
def test_grid_tiler_tissue_mask_filters_tiles(
    synthetic_slide_path: Path,
) -> None:
    reader = open_slide(synthetic_slide_path, mpp=0.5)
    info = reader.info
    reader.close()

    # All-zero mask → no tiles accepted.
    mask_none = np.zeros((info.height, info.width), dtype=bool)
    mask_some = np.zeros_like(mask_none)
    # Enable a 256x256 patch in the centre so exactly one tile survives
    # when min_tissue_fraction >= 0.5 with (256, 256) tiles on a 1024x1024
    # canvas and tile grid aligned.
    mask_some[256:512, 256:512] = True

    tiler = GridTiler(tile_size_px=(256, 256), min_tissue_fraction=0.5)
    none_grid = tiler.plan(info, mask=mask_none)
    some_grid = tiler.plan(info, mask=mask_some)
    assert none_grid.n_tiles == 0
    assert some_grid.n_tiles == 1
    assert some_grid.coordinates[0].x == 256
    assert some_grid.coordinates[0].y == 256


@pytest.mark.unit
def test_grid_tiler_rejects_zero_tile_size() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        GridTiler(tile_size_px=(0, 256))


@pytest.mark.unit
def test_grid_tiler_is_deterministic(synthetic_slide_path: Path) -> None:
    reader = open_slide(synthetic_slide_path, mpp=0.5)
    try:
        tiler = GridTiler(tile_size_px=(128, 128))
        a = tiler.plan(reader.info)
        b = tiler.plan(reader.info)
    finally:
        reader.close()
    assert a.coordinates == b.coordinates
