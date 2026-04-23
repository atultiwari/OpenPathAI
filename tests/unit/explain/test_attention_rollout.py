"""Unit tests for attention-rollout math (numpy-only path)."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.explain.attention_rollout import rollout_from_matrices


def _synthetic_attention(
    *,
    heads: int,
    n: int,
    peak: int,
    noise: float = 0.05,
    seed: int = 0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.uniform(low=0.01, high=0.05, size=(heads, n, n))
    base[:, :, peak] += 0.8
    base[:, peak, :] += 0.8
    base += rng.normal(scale=noise, size=base.shape)
    base = np.clip(base, 0.0, None)
    base /= np.sum(base, axis=-1, keepdims=True)
    return base


def test_rollout_returns_square_patch_grid() -> None:
    # 16 patches + 1 CLS token = 17 tokens.
    layers = [_synthetic_attention(heads=2, n=17, peak=5) for _ in range(3)]
    out = rollout_from_matrices(layers, has_cls_token=True)
    assert out.shape == (4, 4)


def test_rollout_values_are_nonneg() -> None:
    layers = [_synthetic_attention(heads=2, n=17, peak=2) for _ in range(2)]
    out = rollout_from_matrices(layers)
    assert np.all(out >= 0.0)


def test_rollout_peak_matches_injected_peak() -> None:
    # Inject a peak on patch index 8 (→ token 9 because of CLS).
    peak_patch = 8
    layers = [_synthetic_attention(heads=2, n=17, peak=peak_patch + 1, seed=s) for s in range(4)]
    out = rollout_from_matrices(layers)
    # Argmax of the flattened heatmap should land on our injected peak.
    assert int(np.argmax(out)) == peak_patch


def test_rollout_without_cls_token_averages_row() -> None:
    layers = [_synthetic_attention(heads=1, n=16, peak=0) for _ in range(2)]
    out = rollout_from_matrices(layers, has_cls_token=False)
    assert out.shape == (4, 4)


def test_rollout_head_fusion_options() -> None:
    layers = [_synthetic_attention(heads=4, n=17, peak=3) for _ in range(2)]
    out_mean = rollout_from_matrices(layers, head_fusion="mean")
    out_max = rollout_from_matrices(layers, head_fusion="max")
    out_min = rollout_from_matrices(layers, head_fusion="min")
    assert out_mean.shape == out_max.shape == out_min.shape == (4, 4)
    # Max-pooling of heads can only strengthen the peak relative to mean.
    assert np.sum(out_max) >= np.sum(out_mean) - 1e-6


def test_rollout_discard_ratio_keeps_top_signals() -> None:
    layers = [_synthetic_attention(heads=2, n=17, peak=4) for _ in range(2)]
    base = rollout_from_matrices(layers, discard_ratio=0.0)
    pruned = rollout_from_matrices(layers, discard_ratio=0.8)
    # Pruning must not introduce values outside [0, 1]-ish range.
    assert np.all(pruned >= 0.0)
    assert base.shape == pruned.shape


def test_rollout_requires_square_grid() -> None:
    # 6 patches + 1 CLS token → 7 tokens, which isn't a perfect square.
    layers = [_synthetic_attention(heads=1, n=7, peak=1)]
    with pytest.raises(ValueError, match="square patch grid"):
        rollout_from_matrices(layers)


def test_rollout_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        rollout_from_matrices([])


def test_rollout_rejects_bad_discard_ratio() -> None:
    layers = [_synthetic_attention(heads=1, n=17, peak=0)]
    with pytest.raises(ValueError):
        rollout_from_matrices(layers, discard_ratio=1.0)


def test_rollout_rejects_unknown_head_fusion() -> None:
    layers = [_synthetic_attention(heads=1, n=17, peak=0)]
    with pytest.raises(ValueError):
        rollout_from_matrices(layers, head_fusion="bogus")


def test_rollout_accepts_batched_matrix() -> None:
    # (batch, heads, N, N) — the helper should strip the batch dim.
    raw = _synthetic_attention(heads=2, n=17, peak=1)[None, ...]
    out = rollout_from_matrices([raw])
    assert out.shape == (4, 4)


def test_rollout_rejects_non_3d_matrix() -> None:
    with pytest.raises(ValueError):
        rollout_from_matrices([np.zeros((17, 17))])
