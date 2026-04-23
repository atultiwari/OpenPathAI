"""Unit tests for numpy helpers in :mod:`openpathai.explain.base`."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.explain.base import (
    decode_png,
    encode_png,
    heatmap_to_rgb,
    normalise_01,
    overlay_on_tile,
    resize_heatmap,
)


def test_normalise_01_maps_to_unit_range() -> None:
    arr = np.array([[1.0, 3.0], [5.0, 9.0]], dtype=np.float32)
    out = normalise_01(arr)
    assert np.min(out) == pytest.approx(0.0)
    assert np.max(out) == pytest.approx(1.0)


def test_normalise_01_handles_constant() -> None:
    arr = np.full((4, 4), 0.7, dtype=np.float32)
    out = normalise_01(arr)
    np.testing.assert_allclose(out, 0.0)


def test_resize_heatmap_returns_expected_shape() -> None:
    heatmap = np.linspace(0, 1, 16, dtype=np.float32).reshape(4, 4)
    resized = resize_heatmap(heatmap, size=(8, 8))
    assert resized.shape == (8, 8)
    assert np.min(resized) >= 0.0
    assert np.max(resized) <= 1.0


def test_resize_heatmap_rejects_non_2d() -> None:
    with pytest.raises(ValueError):
        resize_heatmap(np.zeros((3, 4, 5), dtype=np.float32), size=(4, 4))


def test_resize_heatmap_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError):
        resize_heatmap(np.zeros((4, 4), dtype=np.float32), size=(0, 4))


def test_heatmap_to_rgb_produces_three_channels() -> None:
    heat = np.linspace(0, 1, 16, dtype=np.float32).reshape(4, 4)
    rgb = heatmap_to_rgb(heat)
    assert rgb.shape == (4, 4, 3)
    assert rgb.dtype == np.uint8


def test_heatmap_to_rgb_rejects_non_2d() -> None:
    with pytest.raises(ValueError):
        heatmap_to_rgb(np.zeros((4, 4, 3), dtype=np.float32))


def test_encode_decode_png_round_trip() -> None:
    rng = np.random.default_rng(0)
    rgb = rng.integers(low=0, high=256, size=(8, 8, 3), dtype=np.uint8)
    blob = encode_png(rgb)
    decoded = decode_png(blob)
    np.testing.assert_array_equal(decoded, rgb)


def test_encode_png_grayscale_round_trip() -> None:
    rng = np.random.default_rng(1)
    gray = rng.integers(low=0, high=256, size=(4, 6), dtype=np.uint8)
    blob = encode_png(gray)
    decoded = decode_png(blob)
    np.testing.assert_array_equal(decoded, gray)


def test_encode_png_rejects_non_uint8() -> None:
    with pytest.raises(ValueError):
        encode_png(np.zeros((4, 4), dtype=np.float32))


def test_encode_png_rejects_bad_shape() -> None:
    with pytest.raises(ValueError):
        encode_png(np.zeros((4, 4, 4), dtype=np.uint8))


def test_decode_png_rejects_bad_base64() -> None:
    with pytest.raises(ValueError):
        decode_png("not-real-base64!!")


def test_decode_png_rejects_non_png_bytes() -> None:
    import base64

    with pytest.raises(ValueError):
        decode_png(base64.b64encode(b"not a PNG").decode("ascii"))


def test_overlay_on_tile_blends_alpha() -> None:
    tile = np.full((4, 4, 3), 200, dtype=np.uint8)
    heatmap = np.full((4, 4), 1.0, dtype=np.float32)
    out = overlay_on_tile(tile, heatmap, alpha=0.5)
    assert out.shape == (4, 4, 3)
    assert out.dtype == np.uint8


def test_overlay_rejects_shape_mismatch() -> None:
    tile = np.zeros((4, 4, 3), dtype=np.uint8)
    heatmap = np.zeros((8, 8), dtype=np.float32)
    with pytest.raises(ValueError):
        overlay_on_tile(tile, heatmap)


def test_overlay_rejects_bad_alpha() -> None:
    tile = np.zeros((4, 4, 3), dtype=np.uint8)
    heatmap = np.zeros((4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        overlay_on_tile(tile, heatmap, alpha=1.5)


def test_overlay_rejects_non_rgb_tile() -> None:
    tile = np.zeros((4, 4, 4), dtype=np.uint8)
    heatmap = np.zeros((4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        overlay_on_tile(tile, heatmap)


def test_overlay_rejects_non_2d_heatmap() -> None:
    tile = np.zeros((4, 4, 3), dtype=np.uint8)
    heatmap = np.zeros((4, 4, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        overlay_on_tile(tile, heatmap)
