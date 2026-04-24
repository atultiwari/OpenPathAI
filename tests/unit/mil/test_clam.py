"""CLAM-SB + the three Phase-13 stubs."""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from openpathai.mil import CLAMSingleBranchAdapter, default_mil_registry  # noqa: E402
from openpathai.mil.clam import (  # noqa: E402
    CLAMMultiBranchStub,
    DSMILStub,
    TransMILStub,
)


def _make_bags(
    n_bags: int = 10, n_per_bag: int = 8, dim: int = 16, seed: int = 0
) -> tuple[list[np.ndarray], np.ndarray]:
    rng = np.random.default_rng(seed)
    bags: list[np.ndarray] = []
    labels: list[int] = []
    for _ in range(n_bags // 2):
        neg = rng.standard_normal((n_per_bag, dim)) - 2.0
        pos = rng.standard_normal((n_per_bag, dim)) + 2.0
        bags.append(neg.astype(np.float32))
        labels.append(0)
        bags.append(pos.astype(np.float32))
        labels.append(1)
    return bags, np.asarray(labels, dtype=np.int64)


def test_clam_sb_fit_runs_and_monotone_loss() -> None:
    bags, labels = _make_bags(seed=1)
    adapter = CLAMSingleBranchAdapter(embedding_dim=16, num_classes=2)
    report = adapter.fit(bags, labels, epochs=4, lr=5e-3, seed=1)
    assert report.aggregator_id == "clam_sb"
    assert report.train_loss_curve[-1] <= report.train_loss_curve[0]


def test_clam_sb_forward_shapes() -> None:
    bags, labels = _make_bags(seed=2)
    adapter = CLAMSingleBranchAdapter(embedding_dim=16, num_classes=2)
    adapter.fit(bags, labels, epochs=2, lr=5e-3, seed=1)
    out = adapter.forward(bags[0])
    assert out.logits.shape == (2,)
    assert out.attention.shape == (bags[0].shape[0],)
    assert float(np.abs(out.attention.sum() - 1.0)) < 1e-5


def test_clam_sb_slide_heatmap_shape() -> None:
    bags, labels = _make_bags(seed=3, n_per_bag=9)
    adapter = CLAMSingleBranchAdapter(embedding_dim=16, num_classes=2)
    adapter.fit(bags, labels, epochs=1, lr=1e-3, seed=1)
    coords = np.array([(y, x) for y in range(3) for x in range(3)], dtype=np.int64)
    heatmap = adapter.slide_heatmap(bags[0], coords)
    assert heatmap.shape == (3, 3)


@pytest.mark.parametrize(
    ("stub_cls", "expected_id"),
    [
        (CLAMMultiBranchStub, "clam_mb"),
        (TransMILStub, "transmil"),
        (DSMILStub, "dsmil"),
    ],
)
def test_stubs_raise_notimplementederror(stub_cls, expected_id) -> None:
    stub = stub_cls(embedding_dim=16, num_classes=2)
    assert stub.id == expected_id
    with pytest.raises(NotImplementedError, match="stub"):
        stub.fit([np.zeros((4, 16), dtype=np.float32)], np.array([0]))
    with pytest.raises(NotImplementedError, match="stub"):
        stub.forward(np.zeros((4, 16), dtype=np.float32))
    with pytest.raises(NotImplementedError, match="stub"):
        stub.slide_heatmap(
            np.zeros((4, 16), dtype=np.float32),
            np.zeros((4, 2), dtype=np.int64),
        )


def test_default_mil_registry_has_five_aggregators() -> None:
    reg = default_mil_registry(embedding_dim=16, num_classes=2)
    assert reg.names() == ["abmil", "clam_mb", "clam_sb", "dsmil", "transmil"]


def test_registry_get_missing_raises() -> None:
    reg = default_mil_registry(embedding_dim=16, num_classes=2)
    with pytest.raises(KeyError, match="unknown"):
        reg.get("not_a_thing")
