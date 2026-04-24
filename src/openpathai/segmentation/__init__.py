"""OpenPathAI — segmentation adapters (Phase 14).

Two protocols:

* :class:`SegmentationAdapter` — closed-vocabulary segmenters (U-Net,
  nnU-Net, SegFormer, HoVer-Net). Input image → mask with
  predefined class ids.
* :class:`PromptableSegmentationAdapter` — SAM / MedSAM / MedSAM2 /
  MedSAM3. Input image + point/box prompt → mask.

The two share the same :class:`SegmentationRegistry` so
``openpathai segmentation list`` shows a unified view.

Fallback semantics mirror Phase 13 + Phase 14 detection: every
gated / weight-backed adapter falls back to the synthetic
segmenter in :mod:`openpathai.segmentation.synthetic` when the
requested model can't be loaded.
"""

from __future__ import annotations

from openpathai.segmentation.adapter import (
    PromptableSegmentationAdapter,
    SegmentationAdapter,
)
from openpathai.segmentation.registry import (
    SegmentationRegistry,
    default_segmentation_registry,
    resolve_segmenter,
)
from openpathai.segmentation.schema import Mask, SegmentationResult
from openpathai.segmentation.synthetic import (
    SyntheticClickSegmenter,
    SyntheticFullTissueSegmenter,
)
from openpathai.segmentation.unet import TinyUNetAdapter

__all__ = [
    "Mask",
    "PromptableSegmentationAdapter",
    "SegmentationAdapter",
    "SegmentationRegistry",
    "SegmentationResult",
    "SyntheticClickSegmenter",
    "SyntheticFullTissueSegmenter",
    "TinyUNetAdapter",
    "default_segmentation_registry",
    "resolve_segmenter",
]
