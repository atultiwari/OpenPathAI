"""Linear-probe training on frozen foundation features (Phase 13).

The standard "how good are my features?" evaluation: freeze the
backbone, extract a feature vector per tile, train a one-layer
linear classifier on top. Because the backbone is frozen, the
probe itself doesn't need torch — a pure-numpy multinomial
logistic regression does the job in a few hundred lines, runs on
any CI cell, and plays cleanly with the Phase-7 calibration
contract.

The returned :class:`LinearProbeReport` is a frozen pydantic
model so downstream Phase-7 `render_pdf`, Phase-8 audit, and the
Phase-3 `TrainingReportArtifact` consumers all see a familiar
shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from openpathai.training.calibration import TemperatureScaler
from openpathai.training.metrics import (
    accuracy,
    expected_calibration_error,
    macro_f1,
)

__all__ = [
    "LinearProbeConfig",
    "LinearProbeReport",
    "fit_linear_probe",
    "predict_proba",
]


@dataclass(frozen=True)
class LinearProbeConfig:
    """Training hyperparameters for :func:`fit_linear_probe`."""

    l2: float = 1e-4
    learning_rate: float = 0.1
    max_iter: int = 500
    tolerance: float = 1e-6
    random_seed: int = 1234
    calibrate: bool = True


class LinearProbeReport(BaseModel):
    """Result of one linear-probe fit. Consumed by CLI + audit + PDF."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    backbone_id: str = Field(min_length=1)
    resolved_backbone_id: str = Field(min_length=1)
    fallback_reason: str
    n_train: int = Field(ge=1)
    n_val: int = Field(ge=0)
    num_classes: int = Field(ge=2)
    accuracy: float = Field(ge=0.0, le=1.0)
    macro_f1: float = Field(ge=0.0, le=1.0)
    ece_before: float = Field(ge=0.0)
    ece_after: float = Field(ge=0.0)
    temperature: float = Field(gt=0.0)
    class_names: tuple[str, ...]
    iterations: int = Field(ge=1)
    final_train_loss: float = Field(ge=0.0)


def _softmax(logits: np.ndarray) -> np.ndarray:
    shift = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shift)
    return exp / exp.sum(axis=1, keepdims=True)


def _nll(probs: np.ndarray, y: np.ndarray) -> float:
    clipped = np.clip(probs, 1e-12, 1.0)
    return float(-np.mean(np.log(clipped[np.arange(len(y)), y])))


def fit_linear_probe(
    features_train: np.ndarray,
    labels_train: np.ndarray,
    *,
    num_classes: int,
    class_names: tuple[str, ...],
    backbone_id: str,
    resolved_backbone_id: str | None = None,
    fallback_reason: str = "ok",
    features_val: np.ndarray | None = None,
    labels_val: np.ndarray | None = None,
    config: LinearProbeConfig | None = None,
) -> LinearProbeReport:
    """Fit a multinomial logistic regression + optional calibration.

    Simple full-batch gradient descent with L2; converges in
    < 500 iterations on the synthetic 3-class benchmarks we ship.
    """
    if config is None:
        config = LinearProbeConfig()
    if features_train.ndim != 2:
        raise ValueError(f"features_train must be 2-D (N, D); got shape {features_train.shape}")
    if labels_train.shape != (features_train.shape[0],):
        raise ValueError(
            f"labels_train shape {labels_train.shape} does not match "
            f"features_train rows {features_train.shape[0]}"
        )
    if len(class_names) != num_classes:
        raise ValueError(
            f"class_names has {len(class_names)} entries but num_classes={num_classes}"
        )

    rng = np.random.default_rng(config.random_seed)
    n_train, feature_dim = features_train.shape
    weights = 0.01 * rng.standard_normal((feature_dim, num_classes))
    bias = np.zeros(num_classes)

    prev_loss = np.inf
    final_iter = 0
    for it in range(1, config.max_iter + 1):
        logits = features_train @ weights + bias
        probs = _softmax(logits)
        # One-hot target.
        onehot = np.zeros_like(probs)
        onehot[np.arange(n_train), labels_train] = 1.0
        grad_logits = (probs - onehot) / n_train
        grad_w = features_train.T @ grad_logits + config.l2 * weights
        grad_b = grad_logits.sum(axis=0)
        weights -= config.learning_rate * grad_w
        bias -= config.learning_rate * grad_b

        loss = _nll(probs, labels_train) + 0.5 * config.l2 * float(np.sum(weights * weights))
        final_iter = it
        if abs(prev_loss - loss) < config.tolerance:
            break
        prev_loss = loss

    # Metrics + calibration on the validation split when supplied,
    # otherwise fall back to training features for both (rare —
    # calibration on train is biased but the contract still holds).
    if features_val is not None and labels_val is not None and len(labels_val) > 0:
        val_logits = features_val @ weights + bias
        val_labels = labels_val
        n_val = len(labels_val)
    else:
        val_logits = features_train @ weights + bias
        val_labels = labels_train
        n_val = 0

    val_probs = _softmax(val_logits)
    acc = float(accuracy(val_labels, val_probs.argmax(axis=1)))
    f1 = float(macro_f1(val_labels, val_probs.argmax(axis=1), num_classes))
    ece_before = float(expected_calibration_error(val_probs, val_labels))

    temperature = 1.0
    ece_after = ece_before
    if config.calibrate and val_logits.shape[0] >= num_classes:
        scaler = TemperatureScaler().fit(val_logits, val_labels)
        temperature = float(scaler.temperature)
        calibrated = _softmax(val_logits / temperature)
        ece_after = float(expected_calibration_error(calibrated, val_labels))

    return LinearProbeReport(
        backbone_id=backbone_id,
        resolved_backbone_id=resolved_backbone_id or backbone_id,
        fallback_reason=fallback_reason,
        n_train=int(n_train),
        n_val=n_val,
        num_classes=int(num_classes),
        accuracy=acc,
        macro_f1=f1,
        ece_before=ece_before,
        ece_after=ece_after,
        temperature=temperature,
        class_names=tuple(class_names),
        iterations=final_iter,
        final_train_loss=float(loss),
    )


def predict_proba(
    features: np.ndarray, weights: np.ndarray, bias: np.ndarray, *, temperature: float = 1.0
) -> np.ndarray:
    """Inference helper shipped for users who cache the fitted weights
    + bias from a previous :func:`fit_linear_probe` (we don't persist
    them in the report, but the fitted artifacts are reconstructible
    from the same seed + features)."""
    logits = features @ weights + bias
    return _softmax(logits / max(temperature, 1e-6))


def _extract_backbone_features(
    adapter: Any,
    images: np.ndarray,
) -> np.ndarray:
    """Thin helper — extract features for a numpy image stack.

    ``images`` has shape ``(N, H, W, 3)`` (uint8) or ``(N, 3, H, W)``
    (float). Returns ``(N, adapter.embedding_dim)``.
    """
    feats = adapter.embed(images)
    arr = np.asarray(feats, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError(f"{type(adapter).__name__}.embed returned shape {arr.shape}; expected 2-D")
    return arr
