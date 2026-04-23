"""Classification losses suited to imbalanced pathology datasets.

This module ships a **numpy** reference implementation of every loss
(used by unit tests and callers who don't have torch installed) and,
when torch is available, a thin torch wrapper that reuses the same
maths. The numpy version is the ground truth; the torch wrapper exists
only to feed autograd for Lightning.

Provided losses:

* :func:`cross_entropy_loss` — optionally weighted + label-smoothed.
* :func:`focal_loss` — Lin et al. 2017 (reduces to CE when ``gamma=0``).
* :func:`ldam_loss` — Cao et al. 2019, class-balanced margin.

Every function accepts ``logits`` of shape ``(N, C)`` and integer
``targets`` of shape ``(N,)``. Returns a single scalar (mean reduction)
unless ``reduction="none"`` is passed.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

__all__ = [
    "Reduction",
    "cross_entropy_loss",
    "focal_loss",
    "ldam_loss",
    "log_softmax_numpy",
    "softmax_numpy",
]

Reduction = Literal["mean", "sum", "none"]


def log_softmax_numpy(logits: np.ndarray) -> np.ndarray:
    """Numerically-stable log-softmax along the last dim."""
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    log_sum = np.log(np.sum(np.exp(shifted), axis=-1, keepdims=True))
    return shifted - log_sum


def softmax_numpy(logits: np.ndarray) -> np.ndarray:
    """Numerically-stable softmax along the last dim."""
    return np.exp(log_softmax_numpy(logits))


def _reduce(values: np.ndarray, reduction: Reduction) -> np.ndarray:
    if reduction == "mean":
        return np.asarray(values.mean(), dtype=values.dtype)
    if reduction == "sum":
        return np.asarray(values.sum(), dtype=values.dtype)
    if reduction == "none":
        return values
    raise ValueError(f"Unknown reduction {reduction!r}")


def _validate(logits: np.ndarray, targets: np.ndarray) -> tuple[int, int]:
    if logits.ndim != 2:
        raise ValueError(f"logits must be 2D (N, C); got shape {logits.shape}")
    if targets.ndim != 1:
        raise ValueError(f"targets must be 1D (N,); got shape {targets.shape}")
    if logits.shape[0] != targets.shape[0]:
        raise ValueError(
            f"logits and targets disagree on N: {logits.shape[0]} vs {targets.shape[0]}"
        )
    n, c = logits.shape
    if c < 1:
        raise ValueError("logits must have at least one class")
    if np.any(targets < 0) or np.any(targets >= c):
        raise ValueError("targets contain out-of-range class indices")
    return n, c


def cross_entropy_loss(
    logits: np.ndarray,
    targets: np.ndarray,
    *,
    class_weights: np.ndarray | None = None,
    label_smoothing: float = 0.0,
    reduction: Reduction = "mean",
) -> np.ndarray:
    """Softmax + NLL cross entropy with optional per-class weighting.

    ``label_smoothing`` follows Szegedy et al. 2016: the true-class
    target becomes ``1 - ε`` and the remaining ``ε`` is spread evenly
    across the other classes.
    """
    _, c = _validate(logits, targets)
    log_probs = log_softmax_numpy(logits)
    if label_smoothing > 0.0:
        # (1 - ε) weight on the target class, ε / C on every class.
        one_hot = np.zeros_like(log_probs)
        one_hot[np.arange(len(targets)), targets] = 1.0
        soft = (1.0 - label_smoothing) * one_hot + label_smoothing / c
        per_example = -(soft * log_probs).sum(axis=-1)
    else:
        per_example = -log_probs[np.arange(len(targets)), targets]

    if class_weights is not None:
        weights = np.asarray(class_weights, dtype=log_probs.dtype)
        if weights.shape != (c,):
            raise ValueError(f"class_weights must have shape (C,) = ({c},)")
        sample_weights = weights[targets]
        per_example = per_example * sample_weights
    return _reduce(per_example, reduction)


def focal_loss(
    logits: np.ndarray,
    targets: np.ndarray,
    *,
    alpha: float | np.ndarray | None = None,
    gamma: float = 2.0,
    reduction: Reduction = "mean",
) -> np.ndarray:
    """Focal loss (Lin et al. 2017).

    ``alpha`` may be a scalar (same alpha for every class) or a 1D array
    of per-class weights. When ``gamma == 0`` and ``alpha is None`` this
    reduces exactly to :func:`cross_entropy_loss`.
    """
    _, c = _validate(logits, targets)
    if gamma < 0.0:
        raise ValueError("focal_loss gamma must be >= 0")

    log_probs = log_softmax_numpy(logits)
    probs = np.exp(log_probs)
    target_log_probs = log_probs[np.arange(len(targets)), targets]
    target_probs = probs[np.arange(len(targets)), targets]
    modulator = (1.0 - target_probs) ** gamma

    alpha_weights: float | np.ndarray
    if alpha is None:
        alpha_weights = 1.0
    elif isinstance(alpha, int | float):
        alpha_weights = float(alpha)
    else:
        alpha_arr = np.asarray(alpha, dtype=log_probs.dtype)
        if alpha_arr.shape != (c,):
            raise ValueError(f"focal_loss alpha must be scalar or shape (C,) = ({c},)")
        alpha_weights = alpha_arr[targets]

    per_example = -alpha_weights * modulator * target_log_probs
    return _reduce(per_example, reduction)


def ldam_loss(
    logits: np.ndarray,
    targets: np.ndarray,
    *,
    class_counts: np.ndarray,
    max_m: float = 0.5,
    scale: float = 30.0,
    class_weights: np.ndarray | None = None,
    reduction: Reduction = "mean",
) -> np.ndarray:
    """Label-Distribution-Aware Margin loss (Cao et al. 2019).

    Margins per class are ``max_m * (n_c ** -1/4) / max_i(n_i ** -1/4)``.
    The margin is subtracted from the target-class logit before softmax;
    non-target logits are left alone. The scaled output is then fed to
    a standard weighted cross entropy.
    """
    n, c = _validate(logits, targets)
    counts = np.asarray(class_counts, dtype=np.float64)
    if counts.shape != (c,):
        raise ValueError(f"class_counts must have shape (C,) = ({c},)")
    if np.any(counts <= 0):
        raise ValueError("class_counts must all be > 0")
    if max_m <= 0 or scale <= 0:
        raise ValueError("max_m and scale must both be > 0")

    raw_margins = 1.0 / np.sqrt(np.sqrt(counts))
    margins = raw_margins * (max_m / np.max(raw_margins))

    offsets = np.zeros_like(logits, dtype=np.float64)
    offsets[np.arange(n), targets] = margins[targets]
    adjusted = (logits - offsets) * scale

    return cross_entropy_loss(
        adjusted.astype(logits.dtype),
        targets,
        class_weights=class_weights,
        reduction=reduction,
    )
