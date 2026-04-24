"""Phase 12 — diversity sampling."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.active_learning.diversity import (
    RandomSampler,
    k_center_greedy,
    random_indices,
)


def _three_clusters(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    centres = np.array([[-5.0, -5.0], [5.0, -5.0], [0.0, 5.0]])
    blocks = []
    for c in centres:
        blocks.append(c + 0.1 * rng.standard_normal((4, 2)))
    return np.vstack(blocks)


def test_k_center_picks_distinct_indices_across_clusters() -> None:
    emb = _three_clusters(seed=0)
    picks = k_center_greedy(emb, 3)
    assert picks.shape == (3,)
    assert len(set(picks.tolist())) == 3
    # Each pick should fall in a different cluster (indices 0..3, 4..7, 8..11).
    clusters = {int(i) // 4 for i in picks}
    assert clusters == {0, 1, 2}


def test_k_center_is_deterministic() -> None:
    emb = _three_clusters(seed=42)
    a = k_center_greedy(emb, 4)
    b = k_center_greedy(emb, 4)
    assert np.array_equal(a, b)


def test_k_center_respects_selected_mask() -> None:
    emb = _three_clusters(seed=1)
    mask = np.zeros(12, dtype=bool)
    mask[0] = True  # pretend index 0 is already labelled
    picks = k_center_greedy(emb, 3, selected_mask=mask)
    assert 0 not in picks.tolist()


def test_k_center_zero_returns_empty() -> None:
    emb = _three_clusters(seed=0)
    assert k_center_greedy(emb, 0).shape == (0,)


def test_k_center_rejects_k_larger_than_pool() -> None:
    emb = _three_clusters(seed=0)
    with pytest.raises(ValueError, match="exceeds N"):
        k_center_greedy(emb, 99)


def test_k_center_rejects_non_2d() -> None:
    with pytest.raises(ValueError, match="2-D"):
        k_center_greedy(np.zeros(8), 2)


def test_random_indices_deterministic_under_seed() -> None:
    a = random_indices(20, 5, seed=7)
    b = random_indices(20, 5, seed=7)
    c = random_indices(20, 5, seed=8)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_random_indices_respects_mask() -> None:
    mask = np.zeros(10, dtype=bool)
    mask[:5] = True  # first half already labelled
    picks = random_indices(10, 3, selected_mask=mask, seed=0)
    assert set(picks.tolist()).issubset(set(range(5, 10)))


def test_random_indices_rejects_over_budget() -> None:
    mask = np.zeros(10, dtype=bool)
    mask[:8] = True
    with pytest.raises(ValueError, match="exceeds"):
        random_indices(10, 5, selected_mask=mask)


def test_random_sampler_wrapper() -> None:
    emb = _three_clusters(seed=0)
    sampler = RandomSampler(seed=3)
    picks = sampler(emb, 2)
    assert picks.shape == (2,)
    assert len(set(picks.tolist())) == 2
