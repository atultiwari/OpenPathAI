"""Diversity sampling in embedding space (Phase 12).

The classical core-set picker from Sener & Savarese (ICLR 2018):
greedy k-center on an ``N`` by ``D`` embedding matrix. We ship a
pure-numpy implementation so the module is import-safe without torch.

Deterministic under a fixed seed when ``selected_mask`` is empty —
ties on equal distance are broken by the smaller index, and the first
pick (when there is no seed set) is the sample nearest the centroid.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import numpy as np

__all__ = [
    "DiversitySampler",
    "RandomSampler",
    "k_center_greedy",
    "random_indices",
]


class DiversitySampler(Protocol):
    """Picks ``k`` indices from an ``N`` by ``D`` embedding matrix.

    ``selected_mask`` (when provided) is a boolean array of length
    ``N`` flagging samples that are **already labelled** — they must
    not be re-picked but still count toward the distance computation.
    """

    def __call__(
        self,
        embeddings: np.ndarray,
        k: int,
        *,
        selected_mask: np.ndarray | None = None,
    ) -> np.ndarray: ...


def _validate_embeddings(
    embeddings: np.ndarray,
    k: int,
    selected_mask: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    if embeddings.ndim != 2:
        raise ValueError(f"embeddings must be 2-D (N, D); got shape {embeddings.shape}")
    n = embeddings.shape[0]
    if k < 0:
        raise ValueError(f"k must be non-negative; got {k}")
    if k > n:
        raise ValueError(f"k={k} exceeds N={n}; cannot pick more than the pool size")

    if selected_mask is None:
        mask = np.zeros(n, dtype=bool)
    else:
        mask = np.asarray(selected_mask, dtype=bool)
        if mask.shape != (n,):
            raise ValueError(f"selected_mask must have shape ({n},); got {mask.shape}")
    return np.asarray(embeddings, dtype=np.float64), mask


def k_center_greedy(
    embeddings: np.ndarray,
    k: int,
    *,
    selected_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Greedy k-center on ``embeddings``.

    Returns a sorted-by-acquisition-order array of length ``k`` with
    new indices (no overlap with ``selected_mask``).

    The first pick (when ``selected_mask`` is all-False) is the sample
    nearest to the overall centroid — a cheap but deterministic
    anchor. Subsequent picks maximise the minimum distance to the
    current selected set, with index-based tie breaking.
    """
    emb, already = _validate_embeddings(embeddings, k, selected_mask)
    n = emb.shape[0]
    if k == 0:
        return np.empty((0,), dtype=np.int64)

    # Distance from each pool point to the nearest *already-selected*
    # sample (∞ when nothing is selected yet).
    if already.any():
        selected_points = emb[already]
        dists = _min_distance_to_set(emb, selected_points)
    else:
        dists = np.full(n, np.inf, dtype=np.float64)

    picked: list[int] = []
    forbidden = already.copy()

    for _ in range(k):
        if np.all(forbidden):
            raise RuntimeError("pool exhausted before k picks — should not happen")

        if np.isinf(dists).all():
            # Cold start: pick the sample nearest to the centroid.
            centroid = emb.mean(axis=0, keepdims=True)
            centroid_dists = _min_distance_to_set(emb, centroid)
            masked = np.where(forbidden, np.inf, centroid_dists)
            idx = int(np.argmin(masked))
        else:
            masked = np.where(forbidden, -np.inf, dists)
            idx = int(np.argmax(masked))

        picked.append(idx)
        forbidden[idx] = True
        # Update running min-distance with the distance to the new pick.
        new_dists = _min_distance_to_set(emb, emb[idx : idx + 1])
        dists = np.minimum(dists, new_dists)

    return np.asarray(picked, dtype=np.int64)


def _min_distance_to_set(points: np.ndarray, members: np.ndarray) -> np.ndarray:
    """Euclidean min-distance from each row of ``points`` to any row of
    ``members``. Shape out: ``(len(points),)``.
    """
    if members.shape[0] == 0:
        return np.full(points.shape[0], np.inf, dtype=np.float64)
    # (N, 1, D) - (1, M, D) → (N, M, D)
    diff = points[:, None, :] - members[None, :, :]
    sq = (diff * diff).sum(axis=2)
    return np.sqrt(sq.min(axis=1))


def random_indices(
    n_total: int,
    k: int,
    *,
    selected_mask: np.ndarray | None = None,
    seed: int = 0,
) -> np.ndarray:
    """Uniformly random pick of ``k`` indices from the unmasked pool."""
    if k < 0:
        raise ValueError(f"k must be non-negative; got {k}")
    if selected_mask is None:
        available = np.arange(n_total)
    else:
        mask = np.asarray(selected_mask, dtype=bool)
        if mask.shape != (n_total,):
            raise ValueError(f"selected_mask must have shape ({n_total},); got {mask.shape}")
        available = np.where(~mask)[0]
    if k > available.size:
        raise ValueError(f"k={k} exceeds available pool size {available.size} after masking")
    rng = np.random.default_rng(seed)
    chosen = rng.choice(available, size=k, replace=False)
    return np.sort(chosen)


class RandomSampler:
    """Callable wrapper around :func:`random_indices` that honours the
    :class:`DiversitySampler` protocol.
    """

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def __call__(
        self,
        embeddings: np.ndarray,
        k: int,
        *,
        selected_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        n = embeddings.shape[0] if embeddings.ndim else 0
        return random_indices(n, k, selected_mask=selected_mask, seed=self.seed)


# Light alias for IDE completions; CLI uses SCORERS-equivalent dispatch.
DIVERSITY_SAMPLERS: dict[str, Callable[..., np.ndarray]] = {
    "random": random_indices,
    "k_center": k_center_greedy,
}
