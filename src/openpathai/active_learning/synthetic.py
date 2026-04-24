"""Synthetic, torch-free :class:`Trainer` for tests + smoke scripts.

The CLI's ``--synthetic`` path and every unit test in
``tests/unit/active_learning/`` plug this in. It embeds each
``tile_id`` into a small deterministic feature vector (hash-seeded)
and fits class prototypes by averaging the labelled features.
Predictions are a softmax over negative Euclidean distance to the
prototypes; a learnable temperature sharpens calibration as more
labelled examples land.

This keeps every loop test:

* deterministic (seed-driven hashing + scalar temperature fit);
* fast (< 1 s end-to-end on CI);
* torch-free (only requires numpy).

Real torch-backed trainers land in Phase 16 alongside the Annotate
GUI — the loop driver is model-agnostic so swapping backends is a
drop-in.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

import numpy as np

from openpathai.active_learning.loop import (
    LabelledExample,
    TrainerFitResult,
)

__all__ = ["PrototypeTrainer"]


def _feature_seed(tile_id: str, dim: int, global_seed: int) -> np.ndarray:
    """Deterministic length-``dim`` feature vector for ``tile_id``.

    Uses a SHA-256 digest seeded with ``global_seed`` so different
    runs get different (but internally consistent) feature spaces.
    """
    key = f"{global_seed}::{tile_id}".encode()
    digest = hashlib.sha256(key).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    return rng.standard_normal(dim)


class PrototypeTrainer:
    """Nearest-prototype classifier with a scalar temperature.

    Implements :class:`openpathai.active_learning.loop.Trainer`.
    """

    def __init__(
        self,
        classes: Sequence[str],
        *,
        embedding_dim: int = 16,
        feature_seed: int = 0,
        label_signal: Mapping[str, np.ndarray] | None = None,
    ) -> None:
        if len(classes) < 2:
            raise ValueError("PrototypeTrainer needs at least 2 classes")
        self.classes = tuple(classes)
        self._dim = embedding_dim
        self._feature_seed = feature_seed
        self._prototypes: np.ndarray | None = None
        self._temperature: float = 1.0
        self._last_train_loss: float = 0.0
        # Class-conditioned "truth signal" — if provided, the feature
        # vector is additively biased toward the prototype of the
        # true class, so more labels → better accuracy/calibration.
        # In practice the CLI always provides this via the pool CSV.
        self._label_signal: dict[str, np.ndarray] = dict(label_signal or {})

    # ─── Public Trainer API ───────────────────────────────────────

    def fit(
        self,
        labelled: Sequence[LabelledExample],
        *,
        max_epochs: int,
        seed: int,
    ) -> TrainerFitResult:
        if not labelled:
            raise ValueError("labelled set is empty")
        features = np.stack([self._feature(e.tile_id) for e in labelled], axis=0)
        label_ids = np.asarray([self.classes.index(e.label) for e in labelled])

        k = len(self.classes)
        protos = np.zeros((k, self._dim), dtype=np.float64)
        counts = np.zeros(k, dtype=np.int64)
        for feat, idx in zip(features, label_ids, strict=True):
            protos[idx] += feat
            counts[idx] += 1
        nonzero = counts > 0
        # Seen classes → averaged prototype; unseen classes fall back
        # to a small deterministic anchor so predict_proba never hits
        # NaNs and unseen-class probability stays low.
        anchor = np.linspace(-1.0, 1.0, self._dim)
        protos[~nonzero] = anchor
        protos[nonzero] /= counts[nonzero, None]
        self._prototypes = protos

        # Temperature: sharpen as more labels land, but clip so
        # predict_proba never fully collapses.
        self._temperature = max(0.25, 2.0 / (1.0 + len(labelled) ** 0.5))

        # Training "loss" = mean distance from each labelled feature
        # to its class prototype (monotone non-increasing as we add
        # more labels).
        pairwise = self._distances(features)
        own = pairwise[np.arange(len(labelled)), label_ids]
        self._last_train_loss = float(own.mean())

        # ``max_epochs`` + ``seed`` are honoured for interface parity
        # but don't change the closed-form prototype fit.
        _ = max_epochs, seed
        return TrainerFitResult(
            epochs_run=int(max_epochs),
            train_loss=self._last_train_loss,
        )

    def predict_proba(self, tile_ids: Sequence[str]) -> np.ndarray:
        if self._prototypes is None:
            raise RuntimeError("call fit() before predict_proba()")
        if not tile_ids:
            return np.zeros((0, len(self.classes)), dtype=np.float64)
        features = np.stack([self._feature(tid) for tid in tile_ids], axis=0)
        dist = self._distances(features)
        logits = -dist / self._temperature
        logits -= logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        return exp / exp.sum(axis=1, keepdims=True)

    def embed(self, tile_ids: Sequence[str]) -> np.ndarray:
        if not tile_ids:
            return np.zeros((0, self._dim), dtype=np.float64)
        return np.stack([self._feature(tid) for tid in tile_ids], axis=0)

    # ─── Helpers ──────────────────────────────────────────────────

    def _feature(self, tile_id: str) -> np.ndarray:
        base = _feature_seed(tile_id, self._dim, self._feature_seed)
        bias = self._label_signal.get(tile_id)
        if bias is None:
            return base
        # Blend 60 % task signal + 40 % noise so the loop has both a
        # real learning gradient *and* a meaningful uncertainty signal.
        return 0.6 * bias + 0.4 * base

    def _distances(self, features: np.ndarray) -> np.ndarray:
        """Euclidean distance from each feature row to each prototype."""
        assert self._prototypes is not None
        diff = features[:, None, :] - self._prototypes[None, :, :]
        return np.sqrt((diff * diff).sum(axis=2))
