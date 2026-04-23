"""Unit tests for the numpy metrics."""

from __future__ import annotations

import numpy as np

from openpathai.training.metrics import (
    accuracy,
    confusion_matrix,
    expected_calibration_error,
    macro_f1,
    reliability_bins,
)


def test_accuracy_perfect() -> None:
    y = np.array([0, 1, 2, 3])
    assert accuracy(y, y) == 1.0


def test_accuracy_half() -> None:
    assert accuracy(np.array([0, 1, 0, 1]), np.array([0, 0, 0, 1])) == 0.75


def test_macro_f1_balanced_perfect() -> None:
    y = np.array([0, 1, 2, 0, 1, 2])
    assert abs(macro_f1(y, y, num_classes=3) - 1.0) < 1e-9


def test_macro_f1_degenerate_predictions() -> None:
    # Predicting class 0 for every sample gives F1 > 0 only for class 0.
    y = np.array([0, 1, 2, 0, 1, 2])
    preds = np.zeros_like(y)
    f1 = macro_f1(y, preds, num_classes=3)
    # Precision for class 0 = 2/6, recall = 2/2 → F1 = 0.5; others zero.
    assert abs(f1 - (0.5 / 3)) < 1e-9


def test_confusion_matrix_shape_and_counts() -> None:
    cm = confusion_matrix(
        np.array([0, 0, 1, 1]),
        np.array([0, 1, 1, 1]),
        num_classes=2,
    )
    np.testing.assert_array_equal(cm, np.array([[1, 1], [0, 2]], dtype=np.int64))


def test_ece_is_zero_on_perfect_calibration() -> None:
    n = 1000
    rng = np.random.default_rng(0)
    # Two-class setup: build probs that match their empirical accuracy.
    probs_c1 = np.linspace(0.5, 0.99, n)
    labels = (rng.uniform(size=n) < probs_c1).astype(np.int64)
    probs = np.stack([1.0 - probs_c1, probs_c1], axis=-1)
    ece = expected_calibration_error(probs, labels, n_bins=15)
    assert ece < 0.05


def test_ece_is_positive_on_overconfident_predictions() -> None:
    # Say the model always predicts 0.99 for class 1 but is right only
    # 50% of the time. ECE should be close to |0.99 - 0.5| = 0.49.
    n = 200
    rng = np.random.default_rng(0)
    labels = rng.integers(low=0, high=2, size=n)
    probs = np.full((n, 2), 0.01, dtype=np.float64)
    probs[:, 1] = 0.99
    ece = expected_calibration_error(probs, labels, n_bins=15)
    assert ece > 0.4


def test_reliability_bins_count_sum_matches_total() -> None:
    probs = np.array(
        [
            [0.1, 0.9],
            [0.4, 0.6],
            [0.55, 0.45],
        ]
    )
    labels = np.array([1, 1, 0])
    _, _, counts = reliability_bins(probs, labels, n_bins=5)
    assert counts.sum() == 3


def test_accuracy_rejects_mismatched_shape() -> None:
    import pytest

    with pytest.raises(ValueError):
        accuracy(np.array([0, 1]), np.array([0, 1, 2]))


def test_accuracy_empty_is_zero() -> None:
    assert accuracy(np.array([], dtype=np.int64), np.array([], dtype=np.int64)) == 0.0


def test_confusion_matrix_rejects_bad_num_classes() -> None:
    import pytest

    with pytest.raises(ValueError):
        confusion_matrix(np.array([0]), np.array([0]), num_classes=0)


def test_confusion_matrix_rejects_shape_mismatch() -> None:
    import pytest

    with pytest.raises(ValueError):
        confusion_matrix(np.array([0, 1]), np.array([0]), num_classes=2)


def test_reliability_bins_rejects_bad_shapes_and_bins() -> None:
    import pytest

    probs = np.array([[0.5, 0.5]])
    with pytest.raises(ValueError):
        reliability_bins(probs.reshape(-1), np.array([0]), n_bins=5)
    with pytest.raises(ValueError):
        reliability_bins(probs, np.array([0, 0]), n_bins=5)
    with pytest.raises(ValueError):
        reliability_bins(probs, np.array([0]), n_bins=0)


def test_expected_calibration_error_empty_is_zero() -> None:
    probs = np.zeros((0, 3))
    labels = np.zeros((0,), dtype=np.int64)
    assert expected_calibration_error(probs, labels) == 0.0
