"""Per-sample uncertainty scorers (Phase 12).

Every scorer is a pure ``(probs: np.ndarray) -> np.ndarray`` function:

* input ``probs`` has shape ``(N, K)`` with rows summing to 1 and
  values in ``[0, 1]``;
* output is a 1-D array of length ``N`` with higher values meaning
  "more uncertain" so that an argsort-descending picks the top-K.

``mc_dropout_variance`` is the one exception — it consumes a stack of
probability tensors (one per MC forward pass) with shape
``(S, N, K)``. The **caller** is responsible for performing the
stochastic forward passes (keeps this module torch-free and trivially
testable).

Keeping the scorers numpy-only means the ``[train]`` extra is **not**
required to import this module; only the CLI path that actually runs
a model needs torch.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

__all__ = [
    "SCORERS",
    "UncertaintyScorer",
    "entropy_score",
    "max_softmax_score",
    "mc_dropout_variance",
]


UncertaintyScorer = Callable[[np.ndarray], np.ndarray]
"""Signature every scorer must honour: ``probs[N, K] -> scores[N]``."""


def _validate_probs(probs: np.ndarray, *, name: str = "probs") -> np.ndarray:
    if probs.ndim != 2:
        raise ValueError(f"{name} must be 2-D (N, K); got shape {probs.shape}")
    if probs.shape[1] < 2:
        raise ValueError(f"{name} must have at least 2 classes; got K={probs.shape[1]}")
    probs = np.asarray(probs, dtype=np.float64)
    if np.any(probs < 0.0) or np.any(probs > 1.0 + 1e-6):
        raise ValueError(f"{name} values must lie in [0, 1]")
    return probs


def max_softmax_score(probs: np.ndarray) -> np.ndarray:
    """Per-sample ``1 - max(softmax)``.

    Falls in ``[0, 1 - 1/K]``. Low on confident rows, high on flat
    rows. This is the default CLI scorer because it is robust across
    calibrations and cheap to compute.
    """
    probs = _validate_probs(probs)
    return 1.0 - probs.max(axis=1)


def entropy_score(probs: np.ndarray) -> np.ndarray:
    """Per-sample Shannon entropy, ``-sum(p * log(p))``.

    Numerically stable: ``p * log(p) = 0`` at ``p = 0`` by convention.
    Falls in ``[0, log(K)]``.
    """
    probs = _validate_probs(probs)
    log_p = np.where(probs > 0.0, np.log(np.clip(probs, 1e-12, 1.0)), 0.0)
    return -np.sum(probs * log_p, axis=1)


def mc_dropout_variance(stacked_probs: np.ndarray) -> np.ndarray:
    """Total per-sample variance across MC-dropout forward passes.

    Input ``stacked_probs`` has shape ``(S, N, K)`` — ``S`` stochastic
    passes, ``N`` samples, ``K`` classes. Output ``(N,)`` is the sum
    over classes of per-class variance across the ``S`` axis.

    Raises :class:`ValueError` when ``S < 2`` (no variance signal).
    """
    if stacked_probs.ndim != 3:
        raise ValueError(f"stacked_probs must be 3-D (S, N, K); got shape {stacked_probs.shape}")
    if stacked_probs.shape[0] < 2:
        raise ValueError(
            "MC-dropout requires at least 2 stochastic forward passes; "
            f"got S={stacked_probs.shape[0]}"
        )
    probs = np.asarray(stacked_probs, dtype=np.float64)
    per_class_var = probs.var(axis=0, ddof=0)  # (N, K)
    return per_class_var.sum(axis=1)


SCORERS: dict[str, UncertaintyScorer] = {
    "max_softmax": max_softmax_score,
    "entropy": entropy_score,
}
"""Registry for CLI-reachable scorers. ``mc_dropout`` is deliberately
excluded here because its signature (``stacked_probs``) differs — the
CLI wires MC-dropout through a dedicated code path that first
generates ``stacked_probs`` via the model."""
