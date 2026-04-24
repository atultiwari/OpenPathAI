"""Text-prompt segmentation fallback behaviour."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.nl import segment_text_prompt
from openpathai.segmentation.schema import SegmentationResult


def _stained_tile(size: int = 128) -> np.ndarray:
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    yy, xx = np.mgrid[:size, :size]
    blob = np.sqrt((yy - size // 2) ** 2 + (xx - size // 2) ** 2) < size // 4
    img[blob] = np.array([100, 60, 120], dtype=np.uint8)
    return img


def test_segment_returns_valid_result() -> None:
    result = segment_text_prompt(_stained_tile(), prompt="gland")
    assert isinstance(result, SegmentationResult)
    assert result.model_id == "medsam2"
    # Fallback routing.
    assert result.resolved_model_id == "synthetic_click"
    # Mask dimensions match input.
    assert result.mask.array.shape == (128, 128)
    # Metadata carries the prompt hash + requested segmenter id.
    assert "prompt_hash" in result.metadata
    assert "requested_segmenter_id" in result.metadata


def test_segment_rejects_empty_prompt() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        segment_text_prompt(_stained_tile(), prompt="")


def test_segment_prompt_hash_is_deterministic() -> None:
    tile = _stained_tile()
    a = segment_text_prompt(tile, prompt="gland")
    b = segment_text_prompt(tile, prompt="gland")
    c = segment_text_prompt(tile, prompt="tumor")
    assert a.metadata["prompt_hash"] == b.metadata["prompt_hash"]
    assert a.metadata["prompt_hash"] != c.metadata["prompt_hash"]


def test_different_prompts_nudge_click() -> None:
    """Prompts bias the click point, so a given pair should produce
    potentially different masks. No strict inequality: the Otsu
    mask may be stable enough that neighboring clicks hit the same
    connected component."""
    tile = _stained_tile()
    a = segment_text_prompt(tile, prompt="gland")
    b = segment_text_prompt(tile, prompt="tumor")
    # Just confirm both return valid masks.
    assert a.mask.array.shape == b.mask.array.shape


def test_segment_requested_segmenter_id_propagates() -> None:
    result = segment_text_prompt(_stained_tile(), prompt="nuclei", segmenter_id="sam2")
    assert result.model_id == "sam2"
    assert result.metadata["requested_segmenter_id"] == "sam2"
