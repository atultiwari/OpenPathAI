"""Unit tests for the training engine (torch-required path)."""

from __future__ import annotations

import importlib.util

import pytest

from openpathai.training.engine import resolve_device

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("torch") is None, reason="torch not installed"
)


def test_resolve_device_returns_cpu_when_preferred() -> None:
    assert resolve_device("cpu") == "cpu"


def test_resolve_device_auto_is_string() -> None:
    value = resolve_device("auto")
    assert value in {"cpu", "cuda", "mps"}


@pytest.fixture()
def tiny_backbone():
    import torch
    import torch.nn as nn

    class _Tiny(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.flatten = nn.Flatten()
            self.head = nn.Linear(3 * 8 * 8, 4)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.head(self.flatten(x))

    return _Tiny


def test_tile_classifier_module_runs_training_step(tiny_backbone) -> None:
    import torch
    import torch.nn.functional as F

    from openpathai.training.engine import TileClassifierModule

    backbone = tiny_backbone()
    module = TileClassifierModule(
        backbone=backbone,
        loss_fn=lambda logits, targets: F.cross_entropy(logits, targets),
    )
    x = torch.zeros(2, 3, 8, 8)
    y = torch.tensor([0, 1])
    loss = module.training_step((x, y))
    assert loss.requires_grad
    loss.backward()
