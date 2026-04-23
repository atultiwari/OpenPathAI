"""Classification metrics — pure numpy.

These power both unit tests (torch-free) and the runtime training loop.
Every metric returns a Python ``float`` so it serialises cleanly into
the run manifest.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "accuracy",
    "confusion_matrix",
    "expected_calibration_error",
    "macro_f1",
    "reliability_bins",
]


def _ensure_1d(y: np.ndarray, name: str) -> np.ndarray:
    arr = np.asarray(y)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1D; got shape {arr.shape}")
    return arr


def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Top-1 accuracy. Returns a fraction in ``[0, 1]``."""
    y_true = _ensure_1d(y_true, "y_true")
    y_pred = _ensure_1d(y_pred, "y_pred")
    if y_true.shape != y_pred.shape:
        raise ValueError(f"shape mismatch: {y_true.shape} vs {y_pred.shape}")
    if len(y_true) == 0:
        return 0.0
    return float(np.mean(y_true == y_pred))


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int) -> np.ndarray:
    """Counts confusion matrix of shape ``(C, C)`` with ``rows=true``."""
    y_true = _ensure_1d(y_true, "y_true").astype(np.int64)
    y_pred = _ensure_1d(y_pred, "y_pred").astype(np.int64)
    if y_true.shape != y_pred.shape:
        raise ValueError("y_true and y_pred must have the same shape")
    if num_classes < 1:
        raise ValueError("num_classes must be >= 1")
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    # Ignore out-of-range labels to be tolerant in noisy inference.
    mask = (y_true >= 0) & (y_true < num_classes) & (y_pred >= 0) & (y_pred < num_classes)
    np.add.at(cm, (y_true[mask], y_pred[mask]), 1)
    return cm


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int) -> float:
    """Unweighted mean per-class F1."""
    cm = confusion_matrix(y_true, y_pred, num_classes)
    tp = np.diag(cm).astype(np.float64)
    fp = cm.sum(axis=0) - tp
    fn = cm.sum(axis=1) - tp
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = np.where(tp + fp > 0, tp / np.maximum(tp + fp, 1.0), 0.0)
        recall = np.where(tp + fn > 0, tp / np.maximum(tp + fn, 1.0), 0.0)
        denom = precision + recall
        f1 = np.where(denom > 0, 2 * precision * recall / np.maximum(denom, 1e-12), 0.0)
    return float(f1.mean())


def reliability_bins(
    probs: np.ndarray,
    y_true: np.ndarray,
    *,
    n_bins: int = 15,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(bin_confidence, bin_accuracy, bin_count)`` arrays.

    Used both by :func:`expected_calibration_error` and by the
    calibration plot Phase 4 draws.
    """
    probs = np.asarray(probs, dtype=np.float64)
    y_true = _ensure_1d(y_true, "y_true").astype(np.int64)
    if probs.ndim != 2:
        raise ValueError(f"probs must be 2D (N, C); got shape {probs.shape}")
    if probs.shape[0] != y_true.shape[0]:
        raise ValueError("probs and y_true disagree on N")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")

    y_pred = np.argmax(probs, axis=-1)
    confidences = np.max(probs, axis=-1)
    accuracies = (y_pred == y_true).astype(np.float64)

    # Right-inclusive bin edges in [0, 1]; np.digitize handles the rest.
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.clip(np.digitize(confidences, edges[1:-1], right=False), 0, n_bins - 1)

    bin_conf = np.zeros(n_bins)
    bin_acc = np.zeros(n_bins)
    bin_count = np.zeros(n_bins, dtype=np.int64)
    for b in range(n_bins):
        mask = bin_ids == b
        count = int(mask.sum())
        bin_count[b] = count
        if count == 0:
            continue
        bin_conf[b] = float(confidences[mask].mean())
        bin_acc[b] = float(accuracies[mask].mean())
    return bin_conf, bin_acc, bin_count


def expected_calibration_error(
    probs: np.ndarray,
    y_true: np.ndarray,
    *,
    n_bins: int = 15,
) -> float:
    """Expected Calibration Error (Guo et al. 2017).

    Returns the size-weighted mean absolute gap between bin confidence
    and bin accuracy.
    """
    bin_conf, bin_acc, bin_count = reliability_bins(probs, y_true, n_bins=n_bins)
    total = bin_count.sum()
    if total == 0:
        return 0.0
    weights = bin_count / total
    return float((weights * np.abs(bin_conf - bin_acc)).sum())
