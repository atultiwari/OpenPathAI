"""MPP-aware grid tiling.

``GridTiler`` produces a deterministic tuple of :class:`TileCoordinate`
over a slide. Tiles are specified in **pixels at target MPP** so that
tiles are physically comparable across slides scanned at different
magnifications.

A mask (boolean ``numpy.ndarray``, typically from
:func:`openpathai.preprocessing.mask.otsu_tissue_mask`) can be provided;
tiles whose mask coverage falls below ``min_tissue_fraction`` are dropped.

The tiler does not read pixels — it plans. A downstream node calls
``SlideReader.read_region`` for each coordinate. This separation keeps
the planner fast and trivially cacheable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from openpathai.io.wsi import SlideInfo

__all__ = [
    "GridTiler",
    "TileCoordinate",
    "TileGrid",
]


@dataclass(frozen=True)
class TileCoordinate:
    """One tile's location in slide (level-0) pixel coordinates."""

    x: int
    y: int
    width: int
    height: int
    row: int
    col: int


class TileGrid(BaseModel):
    """Fully-planned tile grid + its provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slide_path: str
    slide_width: int
    slide_height: int
    tile_size_px: tuple[int, int]
    stride_px: tuple[int, int]
    target_mpp: float | None
    source_mpp: float | None
    coordinates: tuple[TileCoordinate, ...]

    @property
    def n_tiles(self) -> int:
        return len(self.coordinates)


class GridTiler(BaseModel):
    """Plan a grid of tiles over a slide.

    Tile size is given in pixels at ``target_mpp``. When the slide's
    intrinsic MPP differs, tiles are scaled to cover the equivalent
    physical area at level 0.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tile_size_px: tuple[int, int] = (256, 256)
    overlap_px: tuple[int, int] = (0, 0)
    target_mpp: float | None = Field(default=None, gt=0.0)
    min_tissue_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    drop_incomplete: bool = True

    @field_validator("tile_size_px")
    @classmethod
    def _positive_tile(cls, value: tuple[int, int]) -> tuple[int, int]:
        if len(value) != 2:
            raise ValueError("Expected a (width, height) pair")
        if any(v <= 0 for v in value):
            raise ValueError("tile_size_px must be strictly positive")
        return value

    @field_validator("overlap_px")
    @classmethod
    def _nonnegative_overlap(cls, value: tuple[int, int]) -> tuple[int, int]:
        if len(value) != 2:
            raise ValueError("Expected a (width, height) pair")
        if any(v < 0 for v in value):
            raise ValueError("overlap_px must be non-negative")
        return value

    def plan(
        self,
        info: SlideInfo,
        *,
        mask: np.ndarray | None = None,
        mask_mpp: float | None = None,
    ) -> TileGrid:
        tile_w, tile_h = self.tile_size_px
        if tile_w == 0 or tile_h == 0:
            raise ValueError("tile_size_px must have positive dimensions")

        ov_w, ov_h = self.overlap_px
        stride_w = max(1, tile_w - ov_w)
        stride_h = max(1, tile_h - ov_h)

        scale = self._scale_factor(info)
        src_tile_w = max(1, int(round(tile_w * scale)))
        src_tile_h = max(1, int(round(tile_h * scale)))
        src_stride_w = max(1, int(round(stride_w * scale)))
        src_stride_h = max(1, int(round(stride_h * scale)))

        coords: list[TileCoordinate] = []
        row = 0
        y = 0
        while y + (src_tile_h if self.drop_incomplete else 1) <= info.height:
            col = 0
            x = 0
            while x + (src_tile_w if self.drop_incomplete else 1) <= info.width:
                if mask is None or self._mask_accepts(
                    mask, info, x, y, src_tile_w, src_tile_h, mask_mpp
                ):
                    coords.append(
                        TileCoordinate(
                            x=x,
                            y=y,
                            width=src_tile_w,
                            height=src_tile_h,
                            row=row,
                            col=col,
                        )
                    )
                x += src_stride_w
                col += 1
            y += src_stride_h
            row += 1

        return TileGrid(
            slide_path=info.path,
            slide_width=info.width,
            slide_height=info.height,
            tile_size_px=(src_tile_w, src_tile_h),
            stride_px=(src_stride_w, src_stride_h),
            target_mpp=self.target_mpp,
            source_mpp=info.mpp,
            coordinates=tuple(coords),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _scale_factor(self, info: SlideInfo) -> float:
        """Level-0 pixels per target-MPP pixel (``1.0`` when MPPs align)."""
        if self.target_mpp is None or info.mpp is None or info.mpp <= 0:
            return 1.0
        return self.target_mpp / info.mpp

    def _mask_accepts(
        self,
        mask: np.ndarray,
        info: SlideInfo,
        x: int,
        y: int,
        w: int,
        h: int,
        mask_mpp: float | None,
    ) -> bool:
        if mask.ndim != 2:
            raise ValueError("Tissue mask must be 2D")

        mask_h, mask_w = mask.shape
        if mask_mpp is None or info.mpp is None or info.mpp <= 0:
            scale_x = mask_w / info.width
            scale_y = mask_h / info.height
        else:
            scale_x = info.mpp / mask_mpp * (mask_w / info.width)
            scale_y = info.mpp / mask_mpp * (mask_h / info.height)

        mx0 = max(0, int(math.floor(x * scale_x)))
        my0 = max(0, int(math.floor(y * scale_y)))
        mx1 = min(mask_w, int(math.ceil((x + w) * scale_x)))
        my1 = min(mask_h, int(math.ceil((y + h) * scale_y)))
        if mx1 <= mx0 or my1 <= my0:
            return False

        patch = mask[my0:my1, mx0:mx1]
        if patch.size == 0:
            return False
        fraction = float(patch.astype(bool).mean())
        return fraction >= self.min_tissue_fraction
