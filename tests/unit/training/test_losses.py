"""Unit tests for the numpy loss references."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.training.losses import (
    cross_entropy_loss,
    focal_loss,
    ldam_loss,
    log_softmax_numpy,
    softmax_numpy,
)


def _small_batch(seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    logits = rng.normal(size=(8, 4)).astype(np.float32)
    targets = rng.integers(low=0, high=4, size=8)
    return logits, targets


def test_softmax_and_log_softmax_are_consistent() -> None:
    logits, _ = _small_batch()
    probs = softmax_numpy(logits)
    assert np.allclose(probs.sum(axis=-1), 1.0, atol=1e-6)
    log_probs = log_softmax_numpy(logits)
    assert np.allclose(np.exp(log_probs), probs, atol=1e-6)


def test_cross_entropy_matches_hand_math() -> None:
    logits = np.array([[2.0, 1.0, 0.1]], dtype=np.float32)
    targets = np.array([0])
    expected = -np.log(softmax_numpy(logits)[0, 0])
    got = cross_entropy_loss(logits, targets)
    assert np.isclose(got, expected, atol=1e-6)


def test_cross_entropy_class_weights_rescale() -> None:
    logits, targets = _small_batch(seed=1)
    weights = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
    base = cross_entropy_loss(logits, targets)
    weighted = cross_entropy_loss(logits, targets, class_weights=weights)
    assert np.isclose(base, weighted, atol=1e-6)

    # Doubling every weight should double the mean loss.
    doubled = cross_entropy_loss(logits, targets, class_weights=weights * 2)
    assert np.isclose(doubled, 2 * base, atol=1e-6)


def test_cross_entropy_label_smoothing_on_confident_correct_predictions() -> None:
    """When the model is confidently correct, smoothing raises the loss."""
    # Very confident on the correct class → hard CE ≈ 0; smoothing
    # injects ε/C·Σ(-log p_j) on the other classes, which is positive.
    logits = np.array([[10.0, 0.0, 0.0, 0.0]], dtype=np.float32)
    targets = np.array([0])
    hard = cross_entropy_loss(logits, targets, label_smoothing=0.0)
    soft = cross_entropy_loss(logits, targets, label_smoothing=0.1)
    assert soft > hard


def test_focal_loss_reduces_to_ce_when_gamma_zero() -> None:
    logits, targets = _small_batch(seed=3)
    ce = cross_entropy_loss(logits, targets)
    fl = focal_loss(logits, targets, gamma=0.0)
    assert np.isclose(ce, fl, atol=1e-6)


def test_focal_loss_with_gamma_downweights_confident() -> None:
    # A perfectly confident correct prediction should have near-zero focal loss.
    logits = np.array([[10.0, 0.0, 0.0]], dtype=np.float32)
    targets = np.array([0])
    fl = focal_loss(logits, targets, gamma=2.0)
    ce = cross_entropy_loss(logits, targets)
    assert fl < ce


def test_ldam_requires_positive_counts() -> None:
    logits, targets = _small_batch(seed=4)
    with pytest.raises(ValueError):
        ldam_loss(
            logits,
            targets,
            class_counts=np.array([1, 0, 2, 1]),
        )


def test_ldam_lowers_loss_for_common_class_in_imbalanced_setting() -> None:
    """LDAM shrinks the margin on common classes relative to rare ones.

    Under a balanced count, every class gets the max margin. Under an
    imbalanced count, a common class gets a smaller margin (``max_m``
    is reserved for the rarest class), so its per-example LDAM loss
    falls below the balanced baseline.
    """
    logits = np.array([[1.0, 1.0, 1.0, 1.0]], dtype=np.float32)
    targets = np.array([1])  # class 1 is common (count=1000) in imbalanced.
    balanced = ldam_loss(
        logits,
        targets,
        class_counts=np.array([100, 100, 100, 100]),
        scale=1.0,
    )
    imbalanced = ldam_loss(
        logits,
        targets,
        class_counts=np.array([1, 1000, 1000, 1000]),
        scale=1.0,
    )
    assert imbalanced < balanced


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("torch") is None,
    reason="torch not installed",
)
def test_numpy_and_torch_cross_entropy_agree() -> None:
    import torch
    import torch.nn.functional as F

    logits, targets = _small_batch(seed=5)
    numpy_loss = cross_entropy_loss(logits, targets)
    torch_loss = F.cross_entropy(
        torch.from_numpy(logits),
        torch.from_numpy(targets),
    ).item()
    assert np.isclose(numpy_loss, torch_loss, atol=1e-6)


def test_cross_entropy_rejects_bad_shapes() -> None:
    with pytest.raises(ValueError):
        cross_entropy_loss(np.zeros((3,)), np.zeros((3,), dtype=np.int64))
    with pytest.raises(ValueError):
        cross_entropy_loss(np.zeros((3, 2)), np.zeros((4,), dtype=np.int64))
    with pytest.raises(ValueError):
        cross_entropy_loss(np.zeros((3, 2)), np.zeros((3, 2), dtype=np.int64))


def test_cross_entropy_rejects_out_of_range_targets() -> None:
    with pytest.raises(ValueError):
        cross_entropy_loss(np.zeros((2, 3)), np.array([0, 5]))


def test_cross_entropy_rejects_wrong_weight_shape() -> None:
    logits, targets = _small_batch()
    with pytest.raises(ValueError):
        cross_entropy_loss(logits, targets, class_weights=np.ones((2,)))


def test_reduction_sum_and_none() -> None:
    logits, targets = _small_batch()
    per_sample = cross_entropy_loss(logits, targets, reduction="none")
    summed = cross_entropy_loss(logits, targets, reduction="sum")
    mean = cross_entropy_loss(logits, targets, reduction="mean")
    assert per_sample.shape == (logits.shape[0],)
    assert np.isclose(per_sample.sum(), summed, atol=1e-5)
    assert np.isclose(per_sample.mean(), mean, atol=1e-5)


def test_focal_loss_rejects_negative_gamma() -> None:
    logits, targets = _small_batch()
    with pytest.raises(ValueError):
        focal_loss(logits, targets, gamma=-0.1)


def test_focal_loss_per_class_alpha() -> None:
    logits, targets = _small_batch()
    # Per-class alpha array is accepted and scales the loss.
    alpha = np.array([0.5, 1.0, 1.0, 1.0], dtype=np.float32)
    with_alpha = focal_loss(logits, targets, alpha=alpha, gamma=0.0)
    without_alpha = focal_loss(logits, targets, gamma=0.0)
    # Alpha is <= 1 → loss is no larger than the uniform version.
    assert with_alpha <= without_alpha + 1e-6


def test_focal_loss_rejects_wrong_alpha_shape() -> None:
    logits, targets = _small_batch()
    with pytest.raises(ValueError):
        focal_loss(logits, targets, alpha=np.array([0.5, 0.5]))


def test_ldam_rejects_bad_counts_shape() -> None:
    logits, targets = _small_batch()
    with pytest.raises(ValueError):
        ldam_loss(logits, targets, class_counts=np.array([1, 1, 1]))


def test_ldam_rejects_non_positive_max_m_and_scale() -> None:
    logits, targets = _small_batch()
    counts = np.array([10, 10, 10, 10])
    with pytest.raises(ValueError):
        ldam_loss(logits, targets, class_counts=counts, max_m=0.0)
    with pytest.raises(ValueError):
        ldam_loss(logits, targets, class_counts=counts, scale=0.0)
