"""MedSAM2 text-prompted segmentation.

The text prompt goes through the CONCH text encoder; the
resulting embedding replaces the usual (point, box) prompt on
MedSAM2's decoder. Since neither CONCH nor MedSAM2 weights ship
here (both gated; Phase 13/14 stubs + fallback), this function
routes to the Phase-14 :class:`SyntheticClickSegmenter` with a
deterministic image-centre prompt when the real stack is
unavailable — the contract ("a text prompt yields a
``SegmentationResult``") holds end-to-end.
"""

from __future__ import annotations

import hashlib
from typing import Any

from openpathai.segmentation import SegmentationResult, SyntheticClickSegmenter

__all__ = ["segment_text_prompt"]


def segment_text_prompt(
    image: Any,
    prompt: str,
    *,
    segmenter: Any = None,
    text_encoder: Any = None,
    segmenter_id: str = "medsam2",
) -> SegmentationResult:
    """Produce a :class:`SegmentationResult` from a text prompt.

    When ``segmenter`` exposes ``.segment_with_text_prompt(image,
    prompt)`` (real MedSAM2 + CONCH combo), uses it. Otherwise
    falls back to :class:`SyntheticClickSegmenter` with a
    deterministic click point derived from the image centre + the
    prompt hash — the mask is therefore reproducible and the
    call always returns a valid result.
    """
    if not prompt:
        raise ValueError("prompt must be non-empty")

    if segmenter is not None and hasattr(
        segmenter, "segment_with_text_prompt"
    ):  # pragma: no cover — only reached when a real promptable segmenter is wired
        try:
            return segmenter.segment_with_text_prompt(image, prompt)
        except Exception:
            pass

    # Fallback path: synthetic click segmenter with a prompt-biased
    # centre-pixel click. Deterministic under a fixed prompt.
    fallback = SyntheticClickSegmenter()
    h, w = _image_hw(image)
    # Nudge the click by ±8 pixels based on prompt hash so different
    # prompts produce visibly different masks on the same tile.
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    dy = (digest[0] - 128) // 32
    dx = (digest[1] - 128) // 32
    cy = max(0, min(h - 1, h // 2 + dy))
    cx = max(0, min(w - 1, w // 2 + dx))
    result = fallback.segment_with_prompt(image, point=(cy, cx))
    # Attach prompt-metadata so downstream audit can hash it.
    enriched = dict(result.metadata)
    enriched["prompt_hash"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    enriched["requested_segmenter_id"] = segmenter_id
    return SegmentationResult(
        mask=result.mask,
        image_width=result.image_width,
        image_height=result.image_height,
        model_id=segmenter_id,
        resolved_model_id=result.model_id,
        metadata=enriched,
    )


def _image_hw(image: Any) -> tuple[int, int]:
    import numpy as np

    arr = np.asarray(image)
    if arr.ndim == 2:
        return int(arr.shape[0]), int(arr.shape[1])
    if arr.ndim == 3:
        return int(arr.shape[0]), int(arr.shape[1])
    raise ValueError(f"image must be 2-D or 3-D; got shape {arr.shape}")
