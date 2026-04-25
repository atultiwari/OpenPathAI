"""Deep-Zoom Image (DZI) pyramid generator (Phase 21).

OpenSeadragon canonically reads pyramids in the DZI format: an XML
``<sha>.dzi`` descriptor + a sibling ``<sha>_files/<level>/<col>_<row>.png``
tile tree.

This module is a pure-Python generator built on top of
:mod:`openpathai.io.wsi` so any backend the library already supports
(``OpenSlide`` for real WSI, ``Pillow`` for single-plane TIFF / PNG) can
back the viewer without a second image-IO stack.

Generation is lazy + content-addressable:

* Source bytes are hashed (sha256) once.
* The pyramid is materialised on first request under
  ``<root>/<sha>/`` (descriptor + tiles).
* Subsequent requests are static-file reads — no recomputation, no
  in-memory pyramid.
* Per-level work is gated by a directory marker so concurrent tile
  requests do not race.

The generator emits PNG tiles (RGB, lossless) so the viewer overlay
heatmaps share the format. Tile size + overlap follow OpenSeadragon
defaults (``254`` + ``1``) so canonical clients render without
configuration.
"""

from __future__ import annotations

import hashlib
import math
import os
import shutil
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image

from openpathai.io.wsi import open_slide

__all__ = [
    "DEFAULT_OVERLAP",
    "DEFAULT_TILE_SIZE",
    "DZI_NS",
    "DziDescriptor",
    "DziPyramid",
    "compute_levels",
    "hash_file",
    "tile_path",
    "write_descriptor",
]


DEFAULT_TILE_SIZE: int = 254
DEFAULT_OVERLAP: int = 1
DZI_NS = "http://schemas.microsoft.com/deepzoom/2008"

# Cap the DZI base image at this many pixels on the longer axis. Real
# pathology slides are routinely 50_000-100_000 px wide; rendering a
# pyramid from level 0 would mean materialising tens of GB in RAM. The
# Phase-21 viewer is a doctor-usable preview, not a streaming WSI tile
# server — Phase 22+ is the right place for streaming. So we render
# the DZI from a downsampled base; OpenSlide-backed sources pick the
# closest pyramid level, Pillow-backed sources Lanczos-thumbnail.
MAX_DZI_BASE_LONGEST_AXIS: int = 8192


@dataclass(frozen=True)
class DziDescriptor:
    """Wire shape of a DZI ``.dzi`` XML descriptor."""

    width: int
    height: int
    tile_size: int
    overlap: int
    tile_format: str

    def to_xml(self) -> bytes:
        """Render the canonical OpenSeadragon DZI XML."""
        ET.register_namespace("", DZI_NS)
        root = ET.Element(
            f"{{{DZI_NS}}}Image",
            attrib={
                "TileSize": str(self.tile_size),
                "Overlap": str(self.overlap),
                "Format": self.tile_format,
            },
        )
        ET.SubElement(
            root,
            f"{{{DZI_NS}}}Size",
            attrib={"Width": str(self.width), "Height": str(self.height)},
        )
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def hash_file(path: Path, *, chunk: int = 1 << 20) -> str:
    """Return the sha256 hex digest of a file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            blob = fh.read(chunk)
            if not blob:
                break
            h.update(blob)
    return h.hexdigest()


def compute_levels(width: int, height: int) -> int:
    """How many DZI levels fit a `width x height` image.

    OpenSeadragon expects ``ceil(log2(max(w, h))) + 1`` levels, level 0
    being a 1x1 thumbnail.
    """
    largest = max(width, height, 1)
    return math.ceil(math.log2(largest)) + 1


def tile_path(root: Path, slide_id: str, level: int, col: int, row: int, ext: str = "png") -> Path:
    """Canonical DZI tile path under ``root/<slide_id>_files/<level>/<col>_<row>.<ext>``."""
    return root / f"{slide_id}_files" / str(level) / f"{col}_{row}.{ext}"


def write_descriptor(root: Path, slide_id: str, descriptor: DziDescriptor) -> Path:
    """Write the ``<slide_id>.dzi`` descriptor; return its path."""
    out = root / f"{slide_id}.dzi"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(descriptor.to_xml())
    return out


class DziPyramid:
    """Lazy, on-disk DZI pyramid for an image source.

    Two backends are supported transparently:

    * **Slide source** — any path :func:`openpathai.io.wsi.open_slide`
      can open. Used for real whole-slide files and tests' synthetic
      TIFFs.
    * **In-memory array source** — used by the heatmap pipeline to
      pyramid a numpy array without a round-trip through disk first.

    The pyramid lives under ``root / slide_id``. The first request for
    each level renders that level's tiles (idempotent — a directory
    marker prevents duplicate work). Subsequent requests are static
    reads.
    """

    def __init__(
        self,
        root: Path,
        slide_id: str,
        *,
        source_path: Path | None = None,
        array: np.ndarray | None = None,
        tile_size: int = DEFAULT_TILE_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ) -> None:
        if (source_path is None) == (array is None):
            raise ValueError("provide exactly one of source_path or array")
        self._root = root
        self._slide_id = slide_id
        self._source_path = source_path
        self._array = array
        self._tile_size = tile_size
        self._overlap = overlap
        self._lock = threading.Lock()
        self._dir = root / slide_id
        self._dir.mkdir(parents=True, exist_ok=True)
        self._info_path = self._dir / "info.txt"

    @property
    def root(self) -> Path:
        return self._dir

    @property
    def slide_id(self) -> str:
        return self._slide_id

    def _open_base(self) -> tuple[np.ndarray, int, int]:
        """Materialise the DZI base image as an in-memory ``np.uint8``
        RGB array.

        For arrays we use the array as-is (heatmap pipeline). For slide
        files, we downsample to ``MAX_DZI_BASE_LONGEST_AXIS`` so a 4-Gpx
        WSI doesn't blow RAM. OpenSlide-backed slides pick the closest
        pyramid level natively; Pillow-backed slides read the whole
        image and then Lanczos-thumbnail it (Pillow streams TIFF tiles
        internally).
        """
        if self._array is not None:
            arr = self._array
            if arr.ndim == 2:
                arr = np.stack([arr, arr, arr], axis=-1)
            if arr.dtype != np.uint8:
                arr = arr.astype(np.uint8)
            return arr, arr.shape[1], arr.shape[0]
        assert self._source_path is not None
        target_w, target_h = self._dzi_base_size()
        from openpathai.io.wsi import OpenSlideReader

        with open_slide(self._source_path) as slide:
            info = slide.info
            if (
                isinstance(slide, OpenSlideReader)
                and info.level_count > 1
                and (target_w, target_h) != (info.width, info.height)
            ):
                level = self._pick_openslide_level(info, target_w, target_h)
                level_w, level_h = info.level_dimensions[level]
                arr = slide.read_region((0, 0), (level_w, level_h), level=level)
                if (level_w, level_h) != (target_w, target_h):
                    pil = Image.fromarray(arr, mode="RGB").resize(
                        (target_w, target_h), Image.Resampling.LANCZOS
                    )
                    arr = np.asarray(pil, dtype=np.uint8)
            else:
                arr = slide.read_region((0, 0), (info.width, info.height), level=0)
                if arr.shape[:2] != (target_h, target_w):
                    pil = Image.fromarray(arr, mode="RGB").resize(
                        (target_w, target_h), Image.Resampling.LANCZOS
                    )
                    arr = np.asarray(pil, dtype=np.uint8)
        return arr, target_w, target_h

    def _dzi_base_size(self) -> tuple[int, int]:
        """Return the (width, height) of the DZI base image — the slide's
        native resolution clamped to ``MAX_DZI_BASE_LONGEST_AXIS``."""
        assert self._source_path is not None
        with open_slide(self._source_path) as slide:
            width, height = slide.info.width, slide.info.height
        longer = max(width, height, 1)
        if longer <= MAX_DZI_BASE_LONGEST_AXIS:
            return int(width), int(height)
        scale = MAX_DZI_BASE_LONGEST_AXIS / longer
        return max(1, round(width * scale)), max(1, round(height * scale))

    @staticmethod
    def _pick_openslide_level(info: Any, target_w: int, target_h: int) -> int:
        """Return the OpenSlide pyramid level closest to (and >=)
        ``target_w x target_h``. Falls back to the deepest level if no
        level is large enough (rare; means the slide has fewer pixels
        than the target)."""
        for idx, (lw, lh) in enumerate(info.level_dimensions):
            if lw <= target_w * 1.5 and lh <= target_h * 1.5:
                return idx
        return info.level_count - 1

    def descriptor(self) -> DziDescriptor:
        """Return the DZI descriptor without materialising tiles."""
        if self._array is not None:
            height, width = self._array.shape[:2]
        else:
            assert self._source_path is not None
            width, height = self._dzi_base_size()
        return DziDescriptor(
            width=int(width),
            height=int(height),
            tile_size=self._tile_size,
            overlap=self._overlap,
            tile_format="png",
        )

    def descriptor_path(self) -> Path:
        path = self._dir / f"{self._slide_id}.dzi"
        if not path.is_file():
            with self._lock:
                if not path.is_file():
                    write_descriptor(self._dir, self._slide_id, self.descriptor())
        return path

    def tile_bytes(self, level: int, col: int, row: int) -> bytes:
        """Return the raw PNG bytes for a tile, generating the level on
        first call.

        Raises :class:`FileNotFoundError` for out-of-range tiles."""
        path = tile_path(self._dir, self._slide_id, level, col, row, "png")
        if path.is_file():
            return path.read_bytes()
        with self._lock:
            if not path.is_file():
                self._render_level(level)
            if not path.is_file():
                raise FileNotFoundError(
                    f"tile {level}/{col}_{row} out of range for {self._slide_id}"
                )
        return path.read_bytes()

    def _render_level(self, level: int) -> None:
        marker = self._dir / f"{self._slide_id}_files" / str(level) / ".done"
        if marker.is_file():
            return
        base, width, height = self._open_base()
        levels = compute_levels(width, height)
        if level < 0 or level >= levels:
            raise FileNotFoundError(f"DZI level {level} out of range (have {levels} levels)")
        # DZI level i has size ceil(orig / 2 ** (max_level - i)).
        scale = 2 ** (levels - 1 - level)
        lvl_w = max(1, math.ceil(width / scale))
        lvl_h = max(1, math.ceil(height / scale))
        if (lvl_w, lvl_h) != (width, height):
            pil = Image.fromarray(base, mode="RGB")
            pil = pil.resize((lvl_w, lvl_h), Image.Resampling.BILINEAR)
            level_arr = np.asarray(pil, dtype=np.uint8)
        else:
            level_arr = base
        out_dir = self._dir / f"{self._slide_id}_files" / str(level)
        out_dir.mkdir(parents=True, exist_ok=True)
        tile = self._tile_size
        overlap = self._overlap
        cols = max(1, math.ceil(lvl_w / tile))
        rows = max(1, math.ceil(lvl_h / tile))
        for col, row in _iter_grid(cols, rows):
            x0 = max(0, col * tile - overlap)
            y0 = max(0, row * tile - overlap)
            x1 = min(lvl_w, (col + 1) * tile + overlap)
            y1 = min(lvl_h, (row + 1) * tile + overlap)
            crop = level_arr[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            Image.fromarray(crop, mode="RGB").save(
                out_dir / f"{col}_{row}.png", format="PNG", optimize=False
            )
        marker.write_text("done", encoding="utf-8")

    def remove(self) -> None:
        """Drop the on-disk pyramid directory."""
        if self._dir.is_dir():
            shutil.rmtree(self._dir)


def _iter_grid(cols: int, rows: int) -> Iterator[tuple[int, int]]:
    for row in range(rows):
        for col in range(cols):
            yield col, row


def ensure_pyramid_root(root: Path) -> Path:
    """Create the DZI cache root if missing and return it."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def cleanup_orphans(root: Path, valid_ids: set[str]) -> int:
    """Remove pyramid directories whose slide id is no longer registered.

    Returns the number of directories removed. Used by janitors / tests.
    """
    removed = 0
    if not root.is_dir():
        return 0
    for entry in os.scandir(root):
        if not entry.is_dir():
            continue
        if entry.name not in valid_ids:
            shutil.rmtree(Path(entry.path), ignore_errors=True)
            removed += 1
    return removed
