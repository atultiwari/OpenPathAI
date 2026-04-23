"""Unit tests for Integrated Gradients."""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

torch_missing = importlib.util.find_spec("torch") is None
pytestmark = pytest.mark.skipif(torch_missing, reason="torch not installed")


def test_ig_on_linear_model_recovers_sign() -> None:
    import torch
    import torch.nn as nn

    from openpathai.explain.integrated_gradients import integrated_gradients

    torch.manual_seed(0)

    weights = torch.tensor([[1.5, -2.0, 0.5], [-0.3, 0.8, -1.0]])

    class _Linear(nn.Module):
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            flat = x.flatten(1)
            return flat @ weights.T

    tile = torch.tensor([[[[3.0]], [[5.0]], [[-1.0]]]])  # shape (1, 3, 1, 1)

    heat = integrated_gradients(_Linear(), tile, target_class=0, steps=16, signed=True)
    # The integrated gradient equals ``(x - baseline) * w`` since the
    # model is linear. Sign per channel:
    #   ch0: 3 * 1.5 =  4.5  → positive
    #   ch1: 5 * -2  = -10.0 → negative
    #   ch2: -1*0.5  = -0.5  → negative
    # Our heatmap squashes channels via sum, so the scalar is ~-6.0.
    assert heat.shape == (1, 1)
    assert heat[0, 0] < 0.0


def test_ig_absolute_is_normalised() -> None:
    import torch
    import torch.nn as nn

    from openpathai.explain.integrated_gradients import integrated_gradients

    torch.manual_seed(1)

    class _Net(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.conv = nn.Conv2d(3, 4, kernel_size=3, padding=1)
            self.pool = nn.AdaptiveAvgPool2d(1)
            self.fc = nn.Linear(4, 2)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = torch.relu(self.conv(x))
            return self.fc(self.pool(x).flatten(1))

    tile = torch.randn(1, 3, 8, 8)
    heat = integrated_gradients(_Net(), tile, target_class=0, steps=16)
    assert heat.shape == (8, 8)
    assert np.min(heat) == pytest.approx(0.0, abs=1e-6)
    assert np.max(heat) == pytest.approx(1.0, abs=1e-6)


def test_ig_rejects_invalid_steps() -> None:
    import torch
    import torch.nn as nn

    from openpathai.explain.integrated_gradients import integrated_gradients

    class _Net(nn.Module):
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return x.flatten(1).sum(dim=1, keepdim=True).expand(-1, 2)

    with pytest.raises(ValueError):
        integrated_gradients(
            _Net(),
            torch.zeros(1, 3, 4, 4),
            target_class=0,
            steps=0,
        )


def test_ig_rejects_baseline_shape_mismatch() -> None:
    import torch
    import torch.nn as nn

    from openpathai.explain.integrated_gradients import integrated_gradients

    class _Net(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.fc = nn.Linear(48, 2)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.fc(x.flatten(1))

    with pytest.raises(ValueError):
        integrated_gradients(
            _Net(),
            torch.zeros(1, 3, 4, 4),
            target_class=0,
            baseline=torch.zeros(1, 3, 8, 8),
        )
