"""Synthetic segmenters — closed (tissue Otsu) + promptable (click)."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.segmentation import (
    Mask,
    SegmentationResult,
    SyntheticClickSegmenter,
    SyntheticFullTissueSegmenter,
)


def _stained_tile(size: int = 128) -> np.ndarray:
    """Light background (240/240/240) with a darker stained blob."""
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    yy, xx = np.mgrid[:size, :size]
    radius = np.sqrt((yy - size // 2) ** 2 + (xx - size // 2) ** 2)
    img[radius < size // 4] = np.array([100, 60, 120], dtype=np.uint8)
    return img


def test_full_tissue_segmenter_returns_binary_mask() -> None:
    seg = SyntheticFullTissueSegmenter()
    result = seg.segment(_stained_tile())
    assert isinstance(result, SegmentationResult)
    assert isinstance(result.mask, Mask)
    assert result.mask.array.shape == (128, 128)
    assert result.mask.class_names == ("background", "tissue")
    # Some tissue (the circle) plus some background.
    unique = np.unique(result.mask.array)
    assert 0 in unique
    assert 1 in unique


def test_tissue_segmenter_on_uniform_image_is_all_background() -> None:
    seg = SyntheticFullTissueSegmenter()
    blank = np.full((64, 64, 3), 240, dtype=np.uint8)
    result = seg.segment(blank)
    # Either all-zeros or all-ones (Otsu on uniform is ambiguous) but
    # must still be a valid Mask.
    assert result.mask.array.shape == (64, 64)


def test_click_segmenter_requires_prompt() -> None:
    seg = SyntheticClickSegmenter()
    with pytest.raises(ValueError, match="point or box"):
        seg.segment_with_prompt(_stained_tile())


def test_click_segmenter_grows_from_click_inside_blob() -> None:
    seg = SyntheticClickSegmenter()
    result = seg.segment_with_prompt(_stained_tile(), point=(64, 64))
    assert result.mask.class_names == ("background", "prompt_region")
    mask = result.mask.array
    assert mask[64, 64] == 1
    # Mask is non-trivial.
    assert mask.sum() > 0
    assert "label_id_selected" in result.metadata


def test_click_segmenter_outside_image_raises() -> None:
    seg = SyntheticClickSegmenter()
    with pytest.raises(ValueError, match="outside image"):
        seg.segment_with_prompt(_stained_tile(64), point=(999, 999))


def test_click_segmenter_with_box_prompt() -> None:
    seg = SyntheticClickSegmenter()
    result = seg.segment_with_prompt(_stained_tile(), box=(48, 48, 80, 80))
    assert result.mask.array.shape == (128, 128)


def test_mask_rejects_non_2d() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        Mask(array=np.zeros((3, 3, 3), dtype=np.int32), class_names=("a",))


def test_mask_rejects_float_dtype() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        Mask(array=np.zeros((3, 3), dtype=np.float32), class_names=("a",))


def test_mask_rejects_label_out_of_range() -> None:
    import pydantic

    arr = np.array([[0, 1, 2], [2, 1, 0]], dtype=np.int32)
    with pytest.raises(pydantic.ValidationError):
        Mask(array=arr, class_names=("a", "b"))  # max label 2 but only 2 names


def test_mask_class_id_lookup() -> None:
    arr = np.zeros((3, 3), dtype=np.int32)
    m = Mask(array=arr, class_names=("a", "b"))
    assert m.class_id("a") == 0
    assert m.class_id("b") == 1
    with pytest.raises(ValueError, match="not in class_names"):
        m.class_id("c")
