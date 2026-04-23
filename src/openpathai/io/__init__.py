"""I/O primitives for pathology data: cohorts and WSI readers.

Public API:

* :class:`~openpathai.io.cohort.SlideRef` — pointer to one slide + its
  metadata.
* :class:`~openpathai.io.cohort.Cohort` — a hashable, ordered group of
  ``SlideRef`` (master-plan §9.4).
* :func:`~openpathai.io.wsi.open_slide` — factory returning a
  :class:`~openpathai.io.wsi.SlideReader` for a path. Prefers
  openslide/tiatoolbox; falls back to a pure-Pillow reader that
  satisfies tests and simple TIFF fixtures.
"""

from __future__ import annotations

from openpathai.io.cohort import Cohort, SlideRef
from openpathai.io.wsi import (
    PillowSlideReader,
    SlideBackend,
    SlideReader,
    open_slide,
)

__all__ = [
    "Cohort",
    "PillowSlideReader",
    "SlideBackend",
    "SlideReader",
    "SlideRef",
    "open_slide",
]
