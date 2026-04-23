"""Whole-slide image readers.

Two backends, one protocol:

* :class:`OpenSlideReader` wraps ``openslide-python`` (or tiatoolbox's
  :class:`~tiatoolbox.wsicore.wsireader.OpenSlideWSIReader`) for
  real pathology formats — ``.svs``, ``.ndpi``, ``.mrxs``, pyramidal
  ``.tiff``. Imported lazily so systems without native libs stay
  importable.
* :class:`PillowSlideReader` is a pure-Python fallback that treats a
  single-plane TIFF or regular image as a "slide". Used in tests and for
  quick CI runs where installing ``openslide`` is not practical.

:func:`open_slide` picks the best available backend for a path.
"""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

__all__ = [
    "OpenSlideReader",
    "PillowSlideReader",
    "SlideBackend",
    "SlideReader",
    "open_slide",
]


class SlideBackend(str, Enum):
    """Enumeration of available WSI backends."""

    OPENSLIDE = "openslide"
    PILLOW = "pillow"


@dataclass(frozen=True)
class SlideInfo:
    """Summary of a slide's pyramid and physical metadata."""

    path: str
    backend: SlideBackend
    width: int
    height: int
    mpp: float | None
    level_count: int
    level_dimensions: tuple[tuple[int, int], ...]
    level_downsamples: tuple[float, ...]
    properties: dict[str, Any]


class SlideReader(ABC):
    """Abstract WSI reader. Thin by design — tiling lives in
    :mod:`openpathai.tiling.tiler`."""

    @property
    @abstractmethod
    def info(self) -> SlideInfo: ...

    @abstractmethod
    def read_region(
        self,
        location: tuple[int, int],
        size: tuple[int, int],
        level: int = 0,
    ) -> np.ndarray:
        """Return an RGB uint8 tile for the region. Coordinates are
        expressed at the slide's base level (level-0 pixels)."""

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> SlideReader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class PillowSlideReader(SlideReader):
    """Pure-Python fallback: reads any single-layer image as a "slide".

    The whole image is level 0. ``mpp`` can be supplied at construction
    (tests) or read from TIFF resolution tags when available (300 DPI =
    ~84.7 µm/px, so this is informational only).
    """

    def __init__(self, path: str | Path, *, mpp: float | None = None) -> None:
        self._path = str(path)
        image: Image.Image = Image.open(self._path)
        image.load()
        if image.mode != "RGB":
            image = image.convert("RGB")
        self._image: Image.Image | None = image

        inferred_mpp = mpp
        if inferred_mpp is None:
            inferred_mpp = _mpp_from_tiff_tags(image)
        self._mpp = inferred_mpp

        width, height = image.size
        properties: dict[str, Any] = {str(k): v for k, v in image.info.items()}
        self._info = SlideInfo(
            path=self._path,
            backend=SlideBackend.PILLOW,
            width=width,
            height=height,
            mpp=self._mpp,
            level_count=1,
            level_dimensions=((width, height),),
            level_downsamples=(1.0,),
            properties=properties,
        )

    @property
    def info(self) -> SlideInfo:
        return self._info

    def read_region(
        self,
        location: tuple[int, int],
        size: tuple[int, int],
        level: int = 0,
    ) -> np.ndarray:
        if level != 0:
            raise ValueError("PillowSlideReader only supports level=0")
        if self._image is None:
            raise RuntimeError("PillowSlideReader has been closed")
        x, y = location
        w, h = size
        box = (x, y, x + w, y + h)
        tile = self._image.crop(box)
        return np.asarray(tile, dtype=np.uint8)

    def close(self) -> None:
        if self._image is not None:
            try:
                self._image.close()
            finally:
                self._image = None


class OpenSlideReader(SlideReader):
    """Thin adapter over ``openslide-python``.

    The ``openslide`` import is lazy — constructing this class fails
    with a clear error if the native lib isn't installed, so the rest
    of OpenPathAI stays importable on CI workers without openslide.
    """

    def __init__(self, path: str | Path) -> None:
        try:
            openslide = importlib.import_module("openslide")
        except ImportError as exc:
            raise ImportError(
                "openslide-python is required for OpenSlideReader. "
                "Install with `uv sync --extra wsi` (pulls openslide-python + "
                "tiatoolbox) or use PillowSlideReader for simple TIFFs."
            ) from exc
        self._openslide = openslide
        slide = openslide.OpenSlide(str(path))
        self._slide: Any | None = slide
        width, height = slide.dimensions
        props = {str(k): v for k, v in slide.properties.items()}
        mpp_x = props.get(openslide.PROPERTY_NAME_MPP_X)
        mpp = float(mpp_x) if mpp_x is not None else None
        level_dims: tuple[tuple[int, int], ...] = tuple(slide.level_dimensions)
        level_downsamples: tuple[float, ...] = tuple(float(x) for x in slide.level_downsamples)
        self._info = SlideInfo(
            path=str(path),
            backend=SlideBackend.OPENSLIDE,
            width=width,
            height=height,
            mpp=mpp,
            level_count=int(slide.level_count),
            level_dimensions=level_dims,
            level_downsamples=level_downsamples,
            properties=props,
        )

    @property
    def info(self) -> SlideInfo:
        return self._info

    def read_region(
        self,
        location: tuple[int, int],
        size: tuple[int, int],
        level: int = 0,
    ) -> np.ndarray:
        if self._slide is None:
            raise RuntimeError("OpenSlideReader has been closed")
        region = self._slide.read_region(location, level, size).convert("RGB")
        return np.asarray(region, dtype=np.uint8)

    def close(self) -> None:
        if self._slide is not None:
            self._slide.close()
            self._slide = None


def _mpp_from_tiff_tags(image: Image.Image) -> float | None:
    """Best-effort micron-per-pixel from a TIFF's XResolution tag."""
    dpi = image.info.get("dpi")
    if dpi is None:
        return None
    try:
        x_dpi = float(dpi[0])
    except (TypeError, ValueError, IndexError):
        return None
    if x_dpi <= 0:
        return None
    # 1 inch = 25 400 µm. mpp = 25 400 / dpi.
    return 25400.0 / x_dpi


def open_slide(
    path: str | Path,
    *,
    prefer: SlideBackend | None = None,
    mpp: float | None = None,
) -> SlideReader:
    """Open a slide with the best available backend.

    Parameters
    ----------
    path
        Slide path.
    prefer
        Force a specific backend (mainly for tests). If the preferred
        backend is unavailable, raises.
    mpp
        Override/force the slide's micron-per-pixel. Useful when the
        file lacks physical metadata (e.g. synthetic TIFF fixtures).
    """
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Slide file not found: {resolved}")

    if prefer is SlideBackend.PILLOW:
        return PillowSlideReader(resolved, mpp=mpp)
    if prefer is SlideBackend.OPENSLIDE:
        reader = OpenSlideReader(resolved)
        if mpp is not None:
            # Rebind mpp without touching openslide's native handle.
            reader._info = _info_with_mpp(reader.info, mpp)
        return reader

    # Auto-pick: try OpenSlide first, fall back to Pillow on ImportError
    # or unsupported format.
    try:
        reader = OpenSlideReader(resolved)
    except (ImportError, OSError):
        return PillowSlideReader(resolved, mpp=mpp)
    if mpp is not None:
        reader._info = _info_with_mpp(reader.info, mpp)
    return reader


def _info_with_mpp(info: SlideInfo, mpp: float) -> SlideInfo:
    return SlideInfo(
        path=info.path,
        backend=info.backend,
        width=info.width,
        height=info.height,
        mpp=mpp,
        level_count=info.level_count,
        level_dimensions=info.level_dimensions,
        level_downsamples=info.level_downsamples,
        properties=info.properties,
    )
