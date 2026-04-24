"""Tiny pure-torch U-Net — forward-pass shape + determinism anchor."""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from openpathai.segmentation import TinyUNetAdapter  # noqa: E402
from openpathai.segmentation.schema import Mask, SegmentationResult  # noqa: E402


def test_build_returns_torch_module() -> None:
    adapter = TinyUNetAdapter(num_classes=3, class_names=("bg", "gland", "nuclei"))
    module = adapter.build(pretrained=False)
    assert isinstance(module, torch.nn.Module)


def test_segment_returns_matching_shape() -> None:
    adapter = TinyUNetAdapter()
    image = np.random.default_rng(0).integers(0, 255, size=(64, 64, 3), dtype=np.uint8)
    result = adapter.segment(image)
    assert isinstance(result, SegmentationResult)
    assert isinstance(result.mask, Mask)
    assert result.mask.shape == (64, 64)
    assert result.image_width == 64
    assert result.image_height == 64


def test_segment_is_deterministic_under_seed() -> None:
    image = np.random.default_rng(0).integers(0, 255, size=(64, 64, 3), dtype=np.uint8)
    a = TinyUNetAdapter(seed=7).segment(image).mask.array
    b = TinyUNetAdapter(seed=7).segment(image).mask.array
    c = TinyUNetAdapter(seed=8).segment(image).mask.array
    assert np.array_equal(a, b)
    # Different seeds → different random-init weights → likely
    # different predictions. Don't assert inequality strictly (a
    # 2-class argmax on tiny features can collide) — just confirm
    # the mask shape is correct.
    assert c.shape == a.shape


def test_num_classes_mismatch_rejects() -> None:
    with pytest.raises(ValueError, match="must match"):
        TinyUNetAdapter(num_classes=3, class_names=("bg", "fg"))


def test_custom_num_classes_round_trip() -> None:
    adapter = TinyUNetAdapter(num_classes=4, class_names=("bg", "a", "b", "c"), seed=1)
    image = np.random.default_rng(0).integers(0, 255, size=(32, 32, 3), dtype=np.uint8)
    result = adapter.segment(image)
    assert result.mask.class_names == ("bg", "a", "b", "c")


def test_accepts_float_tensor_input() -> None:
    adapter = TinyUNetAdapter(seed=1)
    tensor = torch.rand(3, 32, 32)
    result = adapter.segment(tensor)
    assert result.mask.shape == (32, 32)


def test_accepts_grayscale_image() -> None:
    adapter = TinyUNetAdapter(seed=1)
    gray = np.random.default_rng(0).integers(0, 255, size=(48, 48), dtype=np.uint8)
    result = adapter.segment(gray)
    assert result.mask.shape == (48, 48)
