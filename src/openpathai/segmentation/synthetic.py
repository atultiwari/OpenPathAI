"""License-clean synthetic segmenters for tests + fallback target.

* :class:`SyntheticFullTissueSegmenter` — closed-vocab: Otsu on
  luminance splits background (class 0) vs tissue (class 1).
  Deterministic, license-clean, CPU-fast.
* :class:`SyntheticClickSegmenter` — promptable: takes a (y, x)
  click, grows a region via Otsu + connected-components flood-fill
  from the clicked pixel. Deterministic and always loadable.

Real SAM2 / MedSAM2 weights aren't shippable (HF-gated, 400 MB+);
the promptable stubs in ``promptable/sam.py`` fall back to this
class so the promptable-segmentation code path is exercised end-
to-end in CI without a real weight download.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from openpathai.detection.synthetic import _label_connected_components, _otsu, _to_grayscale
from openpathai.segmentation.schema import Mask, SegmentationResult

__all__ = [
    "SyntheticClickSegmenter",
    "SyntheticFullTissueSegmenter",
]


class SyntheticFullTissueSegmenter:
    """Otsu tissue vs background — closed-vocab demo/fallback."""

    id: str = "synthetic_tissue"
    display_name: str = "Synthetic tissue segmenter (Otsu luminance)"
    gated: bool = False
    weight_source: str | None = None
    input_size: tuple[int, int] = (512, 512)
    num_classes: int = 2
    class_names: tuple[str, ...] = ("background", "tissue")
    tier_compatibility: frozenset[str] = frozenset({"T1", "T2", "T3"})
    vram_gb: float = 0.0
    license: str = "MIT"
    citation: str = "OpenPathAI Phase 14 synthetic segmenter (pure numpy Otsu)."
    promptable: bool = False

    def build(self, pretrained: bool = True) -> None:
        return None

    def segment(self, image: Any) -> SegmentationResult:
        gray = _to_grayscale(image)
        h, w = gray.shape
        mask_bool = _otsu(gray)
        # Tissue is conventionally the *darker* fraction in H&E; invert
        # the Otsu output (which flags the brighter mode as True) when
        # the foreground mean is brighter than the overall mean.
        if mask_bool.mean() > 0.5:
            mask_bool = ~mask_bool
        arr = mask_bool.astype(np.int32)
        return SegmentationResult(
            mask=Mask(array=arr, class_names=self.class_names),
            image_width=int(w),
            image_height=int(h),
            model_id=self.id,
            resolved_model_id=self.id,
        )


class SyntheticClickSegmenter:
    """Click-to-blob promptable segmenter — deterministic fallback."""

    id: str = "synthetic_click"
    display_name: str = "Synthetic click-to-blob segmenter"
    gated: bool = False
    weight_source: str | None = None
    input_size: tuple[int, int] = (1024, 1024)
    tier_compatibility: frozenset[str] = frozenset({"T1", "T2", "T3"})
    vram_gb: float = 0.0
    license: str = "MIT"
    citation: str = "OpenPathAI Phase 14 synthetic click segmenter (Otsu + flood-fill)."
    promptable: bool = True

    def build(self, pretrained: bool = True) -> None:
        return None

    def segment_with_prompt(
        self,
        image: Any,
        *,
        point: tuple[int, int] | None = None,
        box: tuple[int, int, int, int] | None = None,
    ) -> SegmentationResult:
        if point is None and box is None:
            raise ValueError("SyntheticClickSegmenter requires a point or box prompt")
        gray = _to_grayscale(image)
        h, w = gray.shape
        mask_bool = _otsu(gray)
        # H&E convention: tissue is the darker mode. If Otsu flagged
        # the brighter pixels as foreground, invert so the connected-
        # components flood-fill labels tissue regions instead of
        # background.
        if mask_bool.mean() > 0.5:
            mask_bool = ~mask_bool
        labels = _label_connected_components(mask_bool)

        if point is not None:
            py, px = point
            if not (0 <= py < h and 0 <= px < w):
                raise ValueError(f"point {point} outside image (H={h}, W={w})")
            label = int(labels[py, px])
        else:
            # Box → use the centre pixel of the box as the click.
            assert box is not None
            x0, y0, x1, y1 = box
            cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
            label = int(labels[cy, cx]) if 0 <= cy < h and 0 <= cx < w else 0

        mask = (
            (labels == label).astype(np.int32)
            if label > 0
            else np.zeros_like(labels, dtype=np.int32)
        )
        return SegmentationResult(
            mask=Mask(array=mask, class_names=("background", "prompt_region")),
            image_width=int(w),
            image_height=int(h),
            model_id=self.id,
            resolved_model_id=self.id,
            metadata={"label_id_selected": label},
        )
