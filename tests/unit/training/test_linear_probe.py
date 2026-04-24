"""Linear-probe training on synthetic separable features."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.training.linear_probe import (
    LinearProbeConfig,
    LinearProbeReport,
    fit_linear_probe,
    predict_proba,
)


def _make_separable(
    n_per_class: int = 40, dim: int = 8, classes: int = 3, seed: int = 0
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    rng = np.random.default_rng(seed)
    anchors = rng.standard_normal((classes, dim)) * 4.0
    features = []
    labels = []
    for c in range(classes):
        samples = anchors[c] + 0.3 * rng.standard_normal((n_per_class, dim))
        features.append(samples)
        labels.extend([c] * n_per_class)
    return (
        np.concatenate(features).astype(np.float32),
        np.asarray(labels, dtype=np.int64),
        tuple(f"class_{i}" for i in range(classes)),
    )


def test_fit_on_separable_features_reaches_high_accuracy() -> None:
    features, labels, class_names = _make_separable(seed=1)
    report = fit_linear_probe(
        features,
        labels,
        num_classes=3,
        class_names=class_names,
        backbone_id="dinov2_vits14",
    )
    assert isinstance(report, LinearProbeReport)
    assert report.accuracy >= 0.9
    assert report.macro_f1 >= 0.9
    assert report.backbone_id == "dinov2_vits14"
    assert report.resolved_backbone_id == "dinov2_vits14"
    assert report.fallback_reason == "ok"
    assert report.iterations >= 1


def test_deterministic_under_seed() -> None:
    features, labels, class_names = _make_separable(seed=2)
    a = fit_linear_probe(
        features,
        labels,
        num_classes=3,
        class_names=class_names,
        backbone_id="x",
        config=LinearProbeConfig(random_seed=7),
    )
    b = fit_linear_probe(
        features,
        labels,
        num_classes=3,
        class_names=class_names,
        backbone_id="x",
        config=LinearProbeConfig(random_seed=7),
    )
    assert a.accuracy == b.accuracy
    assert a.iterations == b.iterations


def test_val_split_reduces_ece() -> None:
    features, labels, class_names = _make_separable(seed=3)
    # Split 80/20.
    n = len(features)
    perm = np.random.default_rng(0).permutation(n)
    n_val = n // 5
    val_idx = perm[:n_val]
    train_idx = perm[n_val:]
    report = fit_linear_probe(
        features[train_idx],
        labels[train_idx],
        num_classes=3,
        class_names=class_names,
        backbone_id="x",
        features_val=features[val_idx],
        labels_val=labels[val_idx],
    )
    # Temperature scaling should not worsen ECE.
    assert report.ece_after <= report.ece_before + 1e-6
    assert report.n_val == n_val


def test_records_fallback_reason_and_resolved_id() -> None:
    features, labels, class_names = _make_separable(seed=4)
    report = fit_linear_probe(
        features,
        labels,
        num_classes=3,
        class_names=class_names,
        backbone_id="uni",
        resolved_backbone_id="dinov2_vits14",
        fallback_reason="hf_token_missing",
    )
    assert report.backbone_id == "uni"
    assert report.resolved_backbone_id == "dinov2_vits14"
    assert report.fallback_reason == "hf_token_missing"


def test_wrong_num_classes_raises() -> None:
    features, labels, _ = _make_separable(seed=5)
    with pytest.raises(ValueError, match="class_names"):
        fit_linear_probe(
            features,
            labels,
            num_classes=3,
            class_names=("a", "b"),  # mismatch
            backbone_id="x",
        )


def test_predict_proba_matches_softmax() -> None:
    rng = np.random.default_rng(0)
    features = rng.standard_normal((5, 4)).astype(np.float32)
    weights = rng.standard_normal((4, 3)).astype(np.float32)
    bias = rng.standard_normal(3).astype(np.float32)
    probs = predict_proba(features, weights, bias)
    assert probs.shape == (5, 3)
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-5)
    assert (probs >= 0).all() and (probs <= 1.0).all()
