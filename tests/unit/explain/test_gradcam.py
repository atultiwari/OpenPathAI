"""Unit tests for the Grad-CAM family."""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from openpathai.explain.gradcam import eigencam_from_activation, resolve_layer

torch_missing = importlib.util.find_spec("torch") is None


def test_eigencam_from_activation_shape_matches_spatial() -> None:
    rng = np.random.default_rng(0)
    activation = rng.normal(size=(8, 4, 6)).astype(np.float32)
    heat = eigencam_from_activation(activation)
    assert heat.shape == (4, 6)
    assert np.min(heat) >= 0.0
    assert np.max(heat) <= 1.0


def test_eigencam_from_activation_rank_one_is_self() -> None:
    # Build a rank-1 activation stack ``u · v^T`` for every channel.
    base = np.outer(np.linspace(0.1, 1.0, 4), np.linspace(0.1, 1.0, 5)).astype(np.float32)
    channels = np.stack([base * (c + 1.0) for c in range(6)])
    heat = eigencam_from_activation(channels)
    # The dominant SVD direction must peak where ``base`` peaks.
    peak = np.unravel_index(np.argmax(base), base.shape)
    heat_peak = np.unravel_index(np.argmax(heat), heat.shape)
    assert heat_peak == peak


def test_eigencam_from_activation_rejects_non_3d() -> None:
    with pytest.raises(ValueError):
        eigencam_from_activation(np.zeros((4, 4)))


@pytest.mark.skipif(torch_missing, reason="torch not installed")
def test_resolve_layer_string_path_resolves_to_submodule() -> None:
    import torch.nn as nn

    model = nn.Sequential(nn.Conv2d(3, 4, kernel_size=3), nn.ReLU(), nn.Conv2d(4, 4, 3))
    layer = resolve_layer(model, "0")
    assert isinstance(layer, nn.Conv2d)


def test_resolve_layer_rejects_non_module() -> None:
    with pytest.raises(TypeError):
        resolve_layer({}, lambda: 42)


class _FakeLayer:
    """Stand-in for an nn.Module — used to test resolve_layer without torch."""

    def register_forward_hook(self, _fn: object) -> None: ...


def test_resolve_layer_string_path_without_torch() -> None:
    fake = _FakeLayer()
    sub_layer = _FakeLayer()

    class _Model:
        def __init__(self) -> None:
            self.features = [None, fake]
            self.sub = sub_layer

    model = _Model()
    assert resolve_layer(model, "features.1") is fake
    assert resolve_layer(model, "sub") is sub_layer


def test_resolve_layer_direct_module_without_torch() -> None:
    fake = _FakeLayer()
    assert resolve_layer(object(), fake) is fake


def test_resolve_layer_callable_without_torch() -> None:
    fake = _FakeLayer()
    assert resolve_layer(object(), lambda: fake) is fake


def test_gradcam_init_without_torch_binds_model_and_layer() -> None:
    from openpathai.explain.gradcam import EigenCAM, GradCAM, GradCAMPlusPlus

    fake = _FakeLayer()
    model = object()
    for cls in (GradCAM, GradCAMPlusPlus, EigenCAM):
        explainer = cls(model, fake)
        assert explainer.model is model
        assert explainer.target_layer is fake


@pytest.mark.skipif(torch_missing, reason="torch not installed")
def test_gradcam_on_tiny_cnn_is_non_constant() -> None:
    import torch
    import torch.nn as nn

    from openpathai.explain.gradcam import GradCAM

    torch.manual_seed(0)

    class _Tiny(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.conv1 = nn.Conv2d(3, 4, kernel_size=3, padding=1)
            self.conv2 = nn.Conv2d(4, 4, kernel_size=3, padding=1)
            self.pool = nn.AdaptiveAvgPool2d(1)
            self.fc = nn.Linear(4, 2)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = torch.relu(self.conv1(x))
            x = torch.relu(self.conv2(x))
            x = self.pool(x).flatten(1)
            return self.fc(x)

    model = _Tiny()
    tile = torch.randn(1, 3, 16, 16)

    cam = GradCAM(model, target_layer=model.conv2).explain(tile, target_class=0)
    assert cam.shape == (16, 16)
    assert np.min(cam) == pytest.approx(0.0, abs=1e-6)
    assert np.max(cam) == pytest.approx(1.0, abs=1e-6)
    # Heatmap must actually vary — a constant output is a Grad-CAM failure.
    assert np.std(cam) > 0.0


@pytest.mark.skipif(torch_missing, reason="torch not installed")
def test_gradcam_plus_plus_runs_finite() -> None:
    import torch
    import torch.nn as nn

    from openpathai.explain.gradcam import GradCAMPlusPlus

    torch.manual_seed(1)

    class _Tiny(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.conv = nn.Conv2d(3, 4, kernel_size=3, padding=1)
            self.pool = nn.AdaptiveAvgPool2d(1)
            self.fc = nn.Linear(4, 3)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = torch.relu(self.conv(x))
            x = self.pool(x).flatten(1)
            return self.fc(x)

    model = _Tiny()
    tile = torch.randn(1, 3, 16, 16)
    cam = GradCAMPlusPlus(model, target_layer=model.conv).explain(tile, target_class=2)
    assert cam.shape == (16, 16)
    assert np.isfinite(cam).all()


@pytest.mark.skipif(torch_missing, reason="torch not installed")
def test_eigencam_on_tiny_cnn_returns_non_constant() -> None:
    import torch
    import torch.nn as nn

    from openpathai.explain.gradcam import EigenCAM

    torch.manual_seed(2)

    class _Tiny(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.conv = nn.Conv2d(3, 6, kernel_size=3, padding=1)
            self.pool = nn.AdaptiveAvgPool2d(1)
            self.fc = nn.Linear(6, 2)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = torch.relu(self.conv(x))
            x = self.pool(x).flatten(1)
            return self.fc(x)

    model = _Tiny()
    tile = torch.randn(1, 3, 16, 16)
    cam = EigenCAM(model, target_layer=model.conv).explain(tile)
    assert cam.shape == (16, 16)
    assert np.std(cam) > 0.0
