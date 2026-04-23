"""Integrated Gradients (Sundararajan et al. 2017).

For a model ``f`` and an input ``x`` vs. a baseline ``x'``, IG
approximates the path integral of the gradient of ``f`` along the
straight line from ``x'`` to ``x`` via a Riemann sum. The baseline
defaults to zeros (a neutral tile), which is the convention used in
most pathology applications.

The implementation below accumulates gradients in a loop so memory is
bounded regardless of ``steps`` — important when a laptop is asked
for a 64-step IG on a 1024x1024 tile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from openpathai.explain.base import normalise_01, resize_heatmap

if TYPE_CHECKING:  # pragma: no cover - type hints only
    pass

__all__ = ["integrated_gradients"]


def integrated_gradients(  # pragma: no cover - torch only
    model: Any,
    tile: Any,
    target_class: int,
    *,
    baseline: Any | None = None,
    steps: int = 32,
    output_size: tuple[int, int] | None = None,
    signed: bool = False,
) -> np.ndarray:
    """Compute Integrated Gradients for a single tile.

    Parameters
    ----------
    model
        A classification ``torch.nn.Module``. Expects ``(N, C, H, W)``
        input and ``(N, num_classes)`` output.
    tile
        Torch tensor of shape ``(C, H, W)`` or ``(1, C, H, W)``.
    target_class
        Class index to attribute.
    baseline
        Same-shape tensor representing the "uninformative" input.
        Defaults to zeros.
    steps
        Number of Riemann-left interpolation steps.
    output_size
        If given, resize the final absolute-attribution heatmap to this
        ``(H, W)``.
    signed
        If ``True``, return the raw per-pixel attributions (may be
        negative). If ``False`` (default), return the absolute value
        normalised to ``[0, 1]`` so downstream callers see a heatmap.

    Returns
    -------
    np.ndarray
        2D heatmap in ``[0, 1]`` (or raw attributions when ``signed``).
    """
    import torch

    if steps < 1:
        raise ValueError(f"steps must be >= 1; got {steps}")

    if tile.ndim == 3:
        tile = tile.unsqueeze(0)
    baseline_tensor = torch.zeros_like(tile) if baseline is None else baseline
    if tuple(baseline_tensor.shape) != tuple(tile.shape):
        raise ValueError(
            f"baseline and tile must share shape; got "
            f"{tuple(baseline_tensor.shape)} vs {tuple(tile.shape)}"
        )

    was_training = model.training
    model.eval()

    accumulated = torch.zeros_like(tile)
    for step in range(steps):
        alpha = float(step) / steps
        interp = (
            (baseline_tensor + alpha * (tile - baseline_tensor))
            .detach()
            .clone()
            .requires_grad_(True)
        )
        logits = model(interp)
        if logits.ndim != 2:
            raise ValueError(
                f"integrated_gradients expects (N, C) logits; got {tuple(logits.shape)}"
            )
        if target_class < 0 or target_class >= logits.shape[-1]:
            raise IndexError(
                f"target_class {target_class} out of range for {logits.shape[-1]} classes"
            )
        model.zero_grad(set_to_none=True)
        logits[0, target_class].backward(retain_graph=False)
        if interp.grad is None:
            raise RuntimeError(
                "IG could not read gradients back from the input tensor. "
                "Check that the model is differentiable end-to-end."
            )
        accumulated = accumulated + interp.grad.detach()

    average_gradient = accumulated / steps
    attribution = ((tile - baseline_tensor) * average_gradient).detach().cpu().numpy()[0]

    if was_training:
        model.train()

    # Collapse the channel axis — the classifier does not care about
    # channel assignment, and GUI overlays are 2D.
    per_pixel = np.sum(attribution, axis=0) if attribution.ndim == 3 else attribution

    if signed:
        result = per_pixel.astype(np.float32)
    else:
        result = normalise_01(np.abs(per_pixel).astype(np.float32))

    if output_size is not None:
        result = resize_heatmap(result, size=output_size)
    return result
