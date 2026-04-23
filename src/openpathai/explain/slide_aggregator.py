"""Slide-level heatmap aggregation (Phase 4 stub; full DZI in Phase 9).

Given a sequence of per-tile heatmaps plus their slide coordinates,
:class:`SlideHeatmapGrid` paints them onto a canvas of the full slide
dimensions. The result is a ``(H, W)`` float numpy array that Phase 6
(the GUI) can display as a simple overlay and Phase 9 can promote to
OpenSeadragon-compatible DZI tiles.

Pure-numpy, no torch dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "SlideHeatmapGrid",
    "TilePlacement",
]


@dataclass(frozen=True)
class TilePlacement:
    """One tile's heatmap + its top-left coordinates on the slide."""

    heatmap: np.ndarray  # (H, W) float in [0, 1]
    x: int
    y: int

    def __post_init__(self) -> None:
        if self.heatmap.ndim != 2:
            raise ValueError(f"heatmap must be 2D; got shape {self.heatmap.shape}")
        if self.x < 0 or self.y < 0:
            raise ValueError(f"placement coordinates must be >= 0; got ({self.x}, {self.y})")


class SlideHeatmapGrid:
    """Stitch per-tile heatmaps into a slide-wide canvas.

    Overlapping tiles are combined with an aggregation strategy:

    * ``"max"`` — keep the stronger signal (default; robust to
      overlap).
    * ``"mean"`` — average over overlapping tiles (good for smooth
      outputs but requires tracking counts).
    * ``"sum"`` — accumulate raw intensities (for debugging).
    """

    def __init__(
        self,
        *,
        slide_width: int,
        slide_height: int,
        aggregation: str = "max",
    ) -> None:
        if slide_width < 1 or slide_height < 1:
            raise ValueError(f"slide dims must be >=1; got ({slide_width}, {slide_height})")
        if aggregation not in {"max", "mean", "sum"}:
            raise ValueError(f"Unknown aggregation {aggregation!r}")
        self.slide_width = slide_width
        self.slide_height = slide_height
        self.aggregation = aggregation
        self._canvas = np.zeros((slide_height, slide_width), dtype=np.float32)
        self._counts = np.zeros_like(self._canvas, dtype=np.int32)

    def add(self, placement: TilePlacement) -> None:
        """Paint one tile onto the canvas."""
        tile = placement.heatmap.astype(np.float32)
        h, w = tile.shape
        y0 = max(0, placement.y)
        x0 = max(0, placement.x)
        y1 = min(self.slide_height, placement.y + h)
        x1 = min(self.slide_width, placement.x + w)
        if y1 <= y0 or x1 <= x0:
            return  # entirely off-canvas
        ty0 = y0 - placement.y
        tx0 = x0 - placement.x
        sub = tile[ty0 : ty0 + (y1 - y0), tx0 : tx0 + (x1 - x0)]
        target = self._canvas[y0:y1, x0:x1]
        if self.aggregation == "max":
            self._canvas[y0:y1, x0:x1] = np.maximum(target, sub)
        elif self.aggregation == "sum":
            self._canvas[y0:y1, x0:x1] = target + sub
        else:  # "mean"
            self._canvas[y0:y1, x0:x1] = target + sub
            self._counts[y0:y1, x0:x1] += 1

    def stitch(self, placements: list[TilePlacement]) -> np.ndarray:
        """Convenience: add every placement + return the final canvas."""
        for placement in placements:
            self.add(placement)
        return self.canvas

    @property
    def canvas(self) -> np.ndarray:
        if self.aggregation == "mean":
            counts = np.where(self._counts == 0, 1, self._counts)
            return self._canvas / counts
        return self._canvas
