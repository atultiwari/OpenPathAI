"""ABMIL aggregator end-to-end on synthetic bags."""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from openpathai.mil import ABMILAdapter  # noqa: E402


def _make_bags(
    n_bags: int = 12, n_per_bag: int = 8, dim: int = 16, seed: int = 0
) -> tuple[list[np.ndarray], np.ndarray]:
    """Two-class separable bags: class-0 bags contain negative-mean
    instances, class-1 bags positive-mean. Each bag also has some
    random filler tiles so attention must learn to focus."""
    rng = np.random.default_rng(seed)
    bags: list[np.ndarray] = []
    labels: list[int] = []
    for _ in range(n_bags // 2):
        # Class-0 bag.
        salient = rng.standard_normal((2, dim)) - 3.0
        filler = rng.standard_normal((n_per_bag - 2, dim))
        bag = np.vstack([salient, filler]).astype(np.float32)
        rng.shuffle(bag)
        bags.append(bag)
        labels.append(0)
        # Class-1 bag.
        salient = rng.standard_normal((2, dim)) + 3.0
        filler = rng.standard_normal((n_per_bag - 2, dim))
        bag = np.vstack([salient, filler]).astype(np.float32)
        rng.shuffle(bag)
        bags.append(bag)
        labels.append(1)
    return bags, np.asarray(labels, dtype=np.int64)


def test_fit_reduces_loss() -> None:
    bags, labels = _make_bags(seed=1)
    adapter = ABMILAdapter(embedding_dim=16, num_classes=2)
    report = adapter.fit(bags, labels, epochs=5, lr=5e-3, seed=1)
    assert report.aggregator_id == "abmil"
    assert report.n_bags_train == len(bags)
    assert report.epochs_run == 5
    assert len(report.train_loss_curve) == 5
    assert report.train_loss_curve[-1] <= report.train_loss_curve[0]


def test_attention_sums_to_one() -> None:
    bags, labels = _make_bags(seed=2)
    adapter = ABMILAdapter(embedding_dim=16, num_classes=2)
    adapter.fit(bags, labels, epochs=2, lr=5e-3, seed=1)
    out = adapter.forward(bags[0])
    assert out.attention.shape == (bags[0].shape[0],)
    assert out.logits.shape == (2,)
    assert float(np.abs(out.attention.sum() - 1.0)) < 1e-5


def test_forward_before_fit_raises() -> None:
    adapter = ABMILAdapter(embedding_dim=16, num_classes=2)
    with pytest.raises(RuntimeError, match="fit"):
        adapter.forward(np.zeros((4, 16), dtype=np.float32))


def test_slide_heatmap_grid_assembly() -> None:
    bags, labels = _make_bags(seed=3, n_per_bag=9)
    adapter = ABMILAdapter(embedding_dim=16, num_classes=2)
    adapter.fit(bags, labels, epochs=1, lr=1e-3, seed=1)
    coords = np.array([(y, x) for y in range(3) for x in range(3)], dtype=np.int64)
    heatmap = adapter.slide_heatmap(bags[0], coords)
    assert heatmap.shape == (3, 3)
    # Sum of heatmap cells equals attention sum (= 1 under the
    # assumption that every coord is distinct).
    assert float(np.abs(heatmap.sum() - 1.0)) < 1e-5


def test_mismatched_coords_raises() -> None:
    bags, labels = _make_bags(seed=4)
    adapter = ABMILAdapter(embedding_dim=16, num_classes=2)
    adapter.fit(bags, labels, epochs=1, lr=1e-3, seed=1)
    with pytest.raises(ValueError, match="bag size"):
        adapter.slide_heatmap(bags[0], np.array([[0, 0]], dtype=np.int64))


def test_fit_rejects_mismatched_labels() -> None:
    bags, _ = _make_bags(seed=5)
    adapter = ABMILAdapter(embedding_dim=16, num_classes=2)
    with pytest.raises(ValueError, match="same length"):
        adapter.fit(bags, [0, 1], epochs=1)
