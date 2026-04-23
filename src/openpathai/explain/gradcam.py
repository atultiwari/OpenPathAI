"""Grad-CAM family — CNN explainability via forward/backward hooks.

Three closely-related explainers all share the same hook machinery:

* :class:`GradCAM` (Selvaraju et al. 2017) — globally-average-pooled
  gradients weight the activations.
* :class:`GradCAMPlusPlus` (Chattopadhay et al. 2018) — higher-order
  gradient statistics produce better localisation on multi-instance
  inputs.
* :class:`EigenCAM` (Muhammad & Yeasin 2020) — SVD of the activation
  stack; no gradient needed, so robust against zero-gradient
  degeneracies.

Every class takes a ``torch.nn.Module`` plus a *target layer* — either
a direct ``nn.Module`` reference or a dotted attribute path. Torch is
lazy-imported so the module is importable in numpy-only environments.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import numpy as np

from openpathai.explain.base import normalise_01, resize_heatmap

if TYPE_CHECKING:  # pragma: no cover - type hints only
    pass

__all__ = [
    "EigenCAM",
    "GradCAM",
    "GradCAMPlusPlus",
    "resolve_layer",
]


LayerSpec = Any  # ``nn.Module`` or a dotted string path


def resolve_layer(model: Any, layer: LayerSpec) -> Any:
    """Resolve ``layer`` to a concrete submodule of ``model``.

    Accepts:
    * an ``nn.Module`` (returned as-is after an identity check).
    * a dotted attribute path (``"features.7"``).
    * a zero-arg callable returning the submodule.
    """
    if callable(layer) and not hasattr(layer, "register_forward_hook"):
        resolved = layer()
    elif isinstance(layer, str):
        resolved = model
        for part in layer.split("."):
            resolved = getattr(resolved, part) if not part.isdigit() else resolved[int(part)]
    else:
        resolved = layer
    if not hasattr(resolved, "register_forward_hook"):
        raise TypeError(f"Target layer must be an nn.Module; resolved to {type(resolved).__name__}")
    return resolved


@contextmanager
def _hooks(target_layer: Any, capture: dict[str, Any]):  # pragma: no cover - torch only
    """Register forward + full-backward hooks and ensure cleanup."""
    import torch  # noqa: F401

    def _fwd(_module, _input, output) -> None:
        capture["activation"] = output.detach()

    def _bwd(_module, _grad_input, grad_output) -> None:
        capture["gradient"] = grad_output[0].detach()

    fwd_handle = target_layer.register_forward_hook(_fwd)
    bwd_handle = target_layer.register_full_backward_hook(_bwd)
    try:
        yield
    finally:
        fwd_handle.remove()
        bwd_handle.remove()


class _GradCAMBase:
    """Common hook plumbing shared by Grad-CAM / Grad-CAM++."""

    def __init__(self, model: Any, target_layer: LayerSpec) -> None:
        self.model = model
        self.target_layer = resolve_layer(model, target_layer)

    def _forward_with_hooks(  # pragma: no cover - torch only
        self,
        tile: Any,
        target_class: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        capture: dict[str, Any] = {}
        was_training = self.model.training
        self.model.eval()
        if tile.ndim == 3:
            tile = tile.unsqueeze(0)
        if tile.requires_grad is False:
            tile = tile.detach().clone().requires_grad_(True)
        with _hooks(self.target_layer, capture):
            self.model.zero_grad(set_to_none=True)
            logits = self.model(tile)
            if logits.ndim != 2:
                raise ValueError(
                    f"Grad-CAM expects model output (N, C); got shape {tuple(logits.shape)}"
                )
            if target_class < 0 or target_class >= logits.shape[-1]:
                raise IndexError(
                    f"target_class {target_class} out of range for {logits.shape[-1]} classes"
                )
            score = logits[0, target_class]
            score.backward(retain_graph=False)
        if was_training:
            self.model.train()

        if "activation" not in capture or "gradient" not in capture:
            raise RuntimeError("Grad-CAM hooks did not capture activations or gradients")
        activation = capture["activation"][0].detach().cpu().numpy()
        gradient = capture["gradient"][0].detach().cpu().numpy()
        return activation, gradient


class GradCAM(_GradCAMBase):
    """Classical Grad-CAM (Selvaraju et al. 2017)."""

    def explain(  # pragma: no cover - torch only
        self,
        tile: Any,
        target_class: int,
        *,
        output_size: tuple[int, int] | None = None,
    ) -> np.ndarray:
        activation, gradient = self._forward_with_hooks(tile, target_class)
        # Global-average-pool the gradients → per-channel weights.
        weights = np.mean(gradient, axis=(-1, -2))
        cam = np.maximum(np.sum(weights[:, None, None] * activation, axis=0), 0.0)
        cam = normalise_01(cam)
        if output_size is not None:
            cam = resize_heatmap(cam, size=output_size)
        return cam


class GradCAMPlusPlus(_GradCAMBase):
    """Grad-CAM++ (Chattopadhay et al. 2018)."""

    def explain(  # pragma: no cover - torch only
        self,
        tile: Any,
        target_class: int,
        *,
        output_size: tuple[int, int] | None = None,
    ) -> np.ndarray:
        activation, gradient = self._forward_with_hooks(tile, target_class)
        grad2 = gradient**2
        grad3 = gradient**3
        sum_activation = np.sum(activation, axis=(-1, -2), keepdims=True)
        denom = 2.0 * grad2 + sum_activation * grad3 + 1e-7
        alphas = grad2 / denom
        # Only positive gradient contributions count.
        weights = np.sum(alphas * np.maximum(gradient, 0.0), axis=(-1, -2))
        cam = np.maximum(np.sum(weights[:, None, None] * activation, axis=0), 0.0)
        cam = normalise_01(cam)
        if output_size is not None:
            cam = resize_heatmap(cam, size=output_size)
        return cam


class EigenCAM:
    """EigenCAM (Muhammad & Yeasin 2020) — no gradients needed."""

    def __init__(self, model: Any, target_layer: LayerSpec) -> None:
        self.model = model
        self.target_layer = resolve_layer(model, target_layer)

    def explain(  # pragma: no cover - torch only
        self,
        tile: Any,
        target_class: int = 0,
        *,
        output_size: tuple[int, int] | None = None,
    ) -> np.ndarray:
        del target_class  # EigenCAM is class-agnostic.
        import torch

        capture: dict[str, Any] = {}

        def _fwd(_m, _i, output) -> None:
            capture["activation"] = output.detach()

        was_training = self.model.training
        self.model.eval()
        if tile.ndim == 3:
            tile = tile.unsqueeze(0)
        handle = self.target_layer.register_forward_hook(_fwd)
        try:
            with torch.no_grad():
                self.model(tile)
        finally:
            handle.remove()
        if was_training:
            self.model.train()
        if "activation" not in capture:
            raise RuntimeError("EigenCAM forward hook did not capture the activation")

        activation = capture["activation"][0].detach().cpu().numpy()
        return eigencam_from_activation(activation, output_size=output_size)


def eigencam_from_activation(
    activation: np.ndarray,
    *,
    output_size: tuple[int, int] | None = None,
) -> np.ndarray:
    """Compute EigenCAM from a ``(C, H, W)`` activation stack.

    Exposed as a standalone helper so the EigenCAM math is unit-testable
    without torch: supply a synthetic activation stack and verify the
    rank-1-dominant projection directly.
    """
    if activation.ndim != 3:
        raise ValueError(f"activation must be (C, H, W); got {activation.shape}")
    c, h, w = activation.shape
    reshaped = activation.reshape(c, h * w)
    # Centre before SVD so the dominant component captures variance.
    centred = reshaped - np.mean(reshaped, axis=1, keepdims=True)
    # SVD: U (C, C) · S (min) · Vt (min, H*W)
    u, _, vt = np.linalg.svd(centred, full_matrices=False)
    principal = vt[0].reshape(h, w)
    # Sign of the principal direction is arbitrary. Flip so the left
    # singular vector aligns with the per-channel mean of the original
    # (uncentred) activations — i.e. the heatmap correlates with the
    # signal the classifier actually saw.
    channel_mean = np.mean(reshaped, axis=1)
    if float(np.dot(u[:, 0], channel_mean)) < 0.0:
        principal = -principal
    cam = normalise_01(principal)
    if output_size is not None:
        cam = resize_heatmap(cam, size=output_size)
    return cam


# Allow `GradCAM(model, layer)` callers to skip `resolve_layer(...)` —
# the callable form is useful for late-binding the layer when the
# model is wrapped (e.g. in a Lightning module).
def _attr_path(model: Any, path: str) -> Callable[[], Any]:  # pragma: no cover
    def _get() -> Any:
        return resolve_layer(model, path)

    return _get
