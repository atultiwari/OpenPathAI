"""Attention rollout for ViT-style transformer classifiers.

Implements Abnar & Zuidema 2020: combine every layer's self-attention
matrix by (a) adding the identity (to account for the residual
connection), (b) row-normalising, (c) multiplying layer-wise. The
resulting ``(N, N)`` matrix can be read as "how much does token i
depend on token j after L layers?"

For a classifier with a ``CLS`` token, the heatmap is the row of
``CLS``'s dependencies on the patch tokens, reshaped to the patch
grid. Phase 4 ships ViT only; Swin's hierarchical stages break the
naive rollout shape and are scheduled into Phase 13.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from openpathai.explain.base import normalise_01, resize_heatmap

if TYPE_CHECKING:  # pragma: no cover - type hints only
    pass

__all__ = [
    "AttentionRollout",
    "attention_rollout",
    "rollout_from_matrices",
]


def rollout_from_matrices(
    matrices: Sequence[np.ndarray],
    *,
    discard_ratio: float = 0.0,
    head_fusion: str = "mean",
    has_cls_token: bool = True,
) -> np.ndarray:
    """Rollout algorithm given already-captured per-layer attention.

    Exposed as a standalone helper so the core math is unit-testable
    without torch. Each input matrix is ``(num_heads, N, N)``;
    ``head_fusion`` can be ``"mean"``, ``"max"``, or ``"min"``.
    """
    if not matrices:
        raise ValueError("rollout_from_matrices requires at least one attention matrix")
    if discard_ratio < 0.0 or discard_ratio >= 1.0:
        raise ValueError("discard_ratio must be in [0, 1)")

    fused_layers: list[np.ndarray] = []
    for raw in matrices:
        att = np.asarray(raw, dtype=np.float64)
        if att.ndim == 4:  # (batch, heads, N, N) → take the first example
            att = att[0]
        if att.ndim != 3:
            raise ValueError(
                f"Each attention matrix must be (heads, N, N) or (1, heads, N, N); got {att.shape}"
            )
        if head_fusion == "mean":
            fused = np.mean(att, axis=0)
        elif head_fusion == "max":
            fused = np.max(att, axis=0)
        elif head_fusion == "min":
            fused = np.min(att, axis=0)
        else:
            raise ValueError(f"Unknown head_fusion {head_fusion!r}")
        if discard_ratio > 0.0:
            flat = fused.flatten()
            k = max(1, int(flat.size * discard_ratio))
            threshold = np.partition(flat, k - 1)[k - 1]
            mask = fused >= threshold
            fused = fused * mask
        # Add identity (residual) + row-normalise.
        n = fused.shape[-1]
        fused = fused + np.eye(n, dtype=fused.dtype)
        row_sums = np.sum(fused, axis=-1, keepdims=True)
        row_sums = np.where(row_sums == 0, 1.0, row_sums)
        fused = fused / row_sums
        fused_layers.append(fused)

    rollout = fused_layers[0]
    for layer in fused_layers[1:]:
        rollout = layer @ rollout

    cls_row = rollout[0, 1:] if has_cls_token else np.mean(rollout, axis=0)

    num_patches = cls_row.shape[0]
    side = round(np.sqrt(num_patches))
    if side * side != num_patches:
        raise ValueError(f"attention_rollout expects a square patch grid; got {num_patches} tokens")
    return cls_row.reshape(side, side)


def _capture_attention(
    model: Any,
    tile: Any,
) -> list[np.ndarray]:  # pragma: no cover - torch only
    """Forward-hook every attention module and collect softmax outputs."""
    import torch

    captured: list[np.ndarray] = []
    handles: list[Any] = []

    def _hook(_m, _inputs, output):
        # timm's attention modules typically return either ``x`` alone
        # or ``(x, attn)`` depending on their ``return_attention`` flag.
        # We read ``attn`` via the canonical attribute where possible.
        attn_tensor: Any = None
        if isinstance(output, tuple) and len(output) >= 2:
            attn_tensor = output[1]
        elif hasattr(_m, "attn_weights"):
            attn_tensor = getattr(_m, "attn_weights", None)
        if attn_tensor is None:
            return
        captured.append(attn_tensor.detach().cpu().numpy())

    for module in model.modules():
        name = type(module).__name__.lower()
        if "attention" in name or "attn" in name:
            handles.append(module.register_forward_hook(_hook))

    try:
        was_training = model.training
        model.eval()
        with torch.no_grad():
            if tile.ndim == 3:
                tile = tile.unsqueeze(0)
            model(tile)
        if was_training:
            model.train()
    finally:
        for handle in handles:
            handle.remove()

    if not captured:
        raise RuntimeError(
            "attention_rollout could not capture any attention weights. "
            "Models must expose attention via an ``(out, attn)`` tuple or an "
            "``attn_weights`` attribute on their attention submodules."
        )
    return captured


class AttentionRollout:
    """Class wrapper over :func:`attention_rollout`."""

    def __init__(
        self,
        model: Any,
        *,
        head_fusion: str = "mean",
        discard_ratio: float = 0.0,
        has_cls_token: bool = True,
    ) -> None:
        self.model = model
        self.head_fusion = head_fusion
        self.discard_ratio = discard_ratio
        self.has_cls_token = has_cls_token

    def explain(  # pragma: no cover - torch only
        self,
        tile: Any,
        target_class: int = 0,
        *,
        output_size: tuple[int, int] | None = None,
    ) -> np.ndarray:
        del target_class  # rollout is class-agnostic by construction
        return attention_rollout(
            self.model,
            tile,
            head_fusion=self.head_fusion,
            discard_ratio=self.discard_ratio,
            has_cls_token=self.has_cls_token,
            output_size=output_size,
        )


def attention_rollout(  # pragma: no cover - torch only
    model: Any,
    tile: Any,
    *,
    head_fusion: str = "mean",
    discard_ratio: float = 0.0,
    has_cls_token: bool = True,
    output_size: tuple[int, int] | None = None,
) -> np.ndarray:
    """Compute attention rollout for ``tile`` under ``model``.

    Returns a 2D numpy heatmap in ``[0, 1]``, resized to
    ``output_size`` when given.
    """
    matrices = _capture_attention(model, tile)
    rolled = rollout_from_matrices(
        matrices,
        discard_ratio=discard_ratio,
        head_fusion=head_fusion,
        has_cls_token=has_cls_token,
    )
    heatmap = normalise_01(rolled)
    if output_size is not None:
        heatmap = resize_heatmap(heatmap, size=output_size)
    return heatmap
