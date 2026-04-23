"""Tests for :mod:`openpathai.preprocessing.stain`."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.preprocessing.stain import MacenkoNormalizer, MacenkoStainMatrix


@pytest.mark.unit
def test_fit_produces_2x3_stain_matrix(synthetic_he_tile: np.ndarray) -> None:
    norm = MacenkoNormalizer()
    stains = norm.fit(synthetic_he_tile)
    assert isinstance(stains, MacenkoStainMatrix)
    stain_arr, max_c = stains.as_array()
    assert stain_arr.shape == (2, 3)
    assert max_c.shape == (2,)
    # Unit-norm rows (within small tolerance).
    norms = np.linalg.norm(stain_arr, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-6)


@pytest.mark.unit
def test_transform_preserves_shape_and_dtype(
    synthetic_he_tile: np.ndarray,
) -> None:
    norm = MacenkoNormalizer()
    out = norm.transform(synthetic_he_tile)
    assert out.shape == synthetic_he_tile.shape
    assert out.dtype == np.uint8


@pytest.mark.unit
def test_transform_round_trip_is_close_on_reference_target(
    synthetic_he_tile: np.ndarray,
) -> None:
    norm = MacenkoNormalizer()
    # When the target equals the fitted source, the transform should be
    # close to the identity (small deviations come from percentile
    # clipping and integer quantisation).
    fitted = norm.fit(synthetic_he_tile)
    out = norm.transform(synthetic_he_tile, target=fitted)
    diff = np.abs(out.astype(np.int16) - synthetic_he_tile.astype(np.int16))
    # Allow up to 30 mean absolute error in uint8 space; synthetic
    # fixture stays well within this.
    assert diff.mean() < 30.0


@pytest.mark.unit
def test_transform_handles_degenerate_input_gracefully() -> None:
    norm = MacenkoNormalizer()
    blank = np.full((64, 64, 3), 250, dtype=np.uint8)
    out = norm.transform(blank)
    # Degenerate input should fall back to the original (no crash).
    assert out.shape == blank.shape
    assert np.array_equal(out, blank)


@pytest.mark.unit
def test_fit_rejects_non_rgb() -> None:
    norm = MacenkoNormalizer()
    with pytest.raises(ValueError):
        norm.fit(np.zeros((32, 32), dtype=np.uint8))


@pytest.mark.unit
def test_normalizer_is_frozen() -> None:
    norm = MacenkoNormalizer()
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        norm.alpha = 5.0  # type: ignore[misc]
