"""Unit tests for the slide heatmap aggregator."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.explain.slide_aggregator import SlideHeatmapGrid, TilePlacement


def _placement(value: float, x: int, y: int, size: int = 16) -> TilePlacement:
    return TilePlacement(
        heatmap=np.full((size, size), value, dtype=np.float32),
        x=x,
        y=y,
    )


def test_stitch_places_tiles_at_offsets() -> None:
    grid = SlideHeatmapGrid(slide_width=32, slide_height=32, aggregation="max")
    canvas = grid.stitch(
        [
            _placement(1.0, 0, 0),
            _placement(0.5, 16, 16),
        ]
    )
    assert canvas.shape == (32, 32)
    # Corner tile
    assert canvas[0, 0] == pytest.approx(1.0)
    # Far tile
    assert canvas[16, 16] == pytest.approx(0.5)
    # Un-painted region is zero.
    assert canvas[0, 16] == pytest.approx(0.0)


def test_max_aggregation_keeps_stronger_signal() -> None:
    grid = SlideHeatmapGrid(slide_width=16, slide_height=16, aggregation="max")
    grid.add(_placement(0.2, 0, 0))
    grid.add(_placement(0.9, 0, 0))
    assert np.max(grid.canvas) == pytest.approx(0.9)


def test_sum_aggregation_accumulates() -> None:
    grid = SlideHeatmapGrid(slide_width=16, slide_height=16, aggregation="sum")
    grid.add(_placement(0.2, 0, 0))
    grid.add(_placement(0.3, 0, 0))
    assert grid.canvas[0, 0] == pytest.approx(0.5)


def test_mean_aggregation_averages_overlap() -> None:
    grid = SlideHeatmapGrid(slide_width=16, slide_height=16, aggregation="mean")
    grid.add(_placement(0.2, 0, 0))
    grid.add(_placement(0.8, 0, 0))
    np.testing.assert_allclose(grid.canvas[0, 0], 0.5)


def test_partially_off_canvas_tile_is_clipped() -> None:
    grid = SlideHeatmapGrid(slide_width=16, slide_height=16)
    # Tile at (8, 8) with 16x16 extent runs 8px off on bottom-right.
    grid.add(_placement(1.0, 8, 8, size=16))
    assert grid.canvas[15, 15] == pytest.approx(1.0)
    assert grid.canvas[0, 0] == pytest.approx(0.0)


def test_entirely_off_canvas_tile_is_ignored() -> None:
    grid = SlideHeatmapGrid(slide_width=16, slide_height=16)
    grid.add(_placement(1.0, 100, 100, size=4))
    assert np.max(grid.canvas) == pytest.approx(0.0)


def test_rejects_bad_aggregation() -> None:
    with pytest.raises(ValueError):
        SlideHeatmapGrid(slide_width=16, slide_height=16, aggregation="median")


def test_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValueError):
        SlideHeatmapGrid(slide_width=0, slide_height=16)


def test_tile_placement_rejects_non_2d_heatmap() -> None:
    with pytest.raises(ValueError):
        TilePlacement(heatmap=np.zeros((4, 4, 4), dtype=np.float32), x=0, y=0)


def test_tile_placement_rejects_negative_offsets() -> None:
    with pytest.raises(ValueError):
        TilePlacement(heatmap=np.zeros((4, 4), dtype=np.float32), x=-1, y=0)
