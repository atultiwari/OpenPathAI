"""Pipeline-facing explainability nodes.

Three nodes are registered:

* ``explain.gradcam`` — drives :class:`GradCAM` on a supplied torch
  classifier + tile. Input + output are content-hashed so identical
  parameters hit the cache on rerun.
* ``explain.attention_rollout`` — ViT attention rollout.
* ``explain.integrated_gradients`` — IG attribution.

Like :mod:`openpathai.training.node`, the node functions look up the
runtime model + tile tensors from a module-level store so pydantic
inputs stay JSON-friendly and cacheable.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from openpathai.explain.artifacts import HeatmapArtifact
from openpathai.explain.base import encode_png, overlay_on_tile
from openpathai.pipeline.node import node
from openpathai.pipeline.schema import canonical_sha256

__all__ = [
    "ExplainGradCAMInput",
    "ExplainIntegratedGradientsInput",
    "ExplainRolloutInput",
    "clear_explain_targets",
    "lookup_explain_target",
    "register_explain_target",
]


class _ExplainTarget:
    """Runtime bundle: the torch model + tile tensor to explain."""

    __slots__ = ("model", "target_layer", "tile", "tile_rgb")

    def __init__(
        self,
        model: Any,
        tile: Any,
        *,
        target_layer: Any | None = None,
        tile_rgb: Any | None = None,
    ) -> None:
        self.model = model
        self.tile = tile
        self.target_layer = target_layer
        self.tile_rgb = tile_rgb


_TARGET_STORE: dict[str, _ExplainTarget] = {}


def _tile_sum(tile: Any) -> float:
    """Best-effort scalar summary of a tile for digest input.

    Accepts torch tensors, numpy arrays, or anything else with a
    callable ``.sum()``. Returns ``0.0`` for unsupported types so the
    digest remains computable.
    """
    summer = getattr(tile, "sum", None)
    if not callable(summer):
        return 0.0
    raw = summer()
    item = getattr(raw, "item", None)
    if callable(item):
        try:
            return float(item())  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def register_explain_target(
    model: Any,
    tile: Any,
    *,
    target_layer: Any | None = None,
    tile_rgb: Any | None = None,
) -> str:
    """Register a (model, tile) pair; return the digest to reference it."""
    payload: dict[str, Any] = {
        "model_id": id(model),
        "tile_shape": list(getattr(tile, "shape", [])),
        "tile_sum": _tile_sum(tile),
        "layer": repr(target_layer) if target_layer is not None else None,
    }
    digest = canonical_sha256(payload)
    _TARGET_STORE[digest] = _ExplainTarget(
        model,
        tile,
        target_layer=target_layer,
        tile_rgb=tile_rgb,
    )
    return digest


def lookup_explain_target(digest: str) -> _ExplainTarget:
    try:
        return _TARGET_STORE[digest]
    except KeyError as exc:
        raise KeyError(
            f"No explain target registered for {digest!r}. Call "
            f"openpathai.explain.node.register_explain_target(...) first."
        ) from exc


def clear_explain_targets() -> None:
    _TARGET_STORE.clear()


# --------------------------------------------------------------------------- #
# Node input schemas
# --------------------------------------------------------------------------- #


class ExplainGradCAMInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_digest: str = Field(min_length=1)
    model_card: str
    target_class: int = Field(ge=0)
    output_size: tuple[int, int] | None = None
    kind: str = Field(default="gradcam")  # "gradcam" | "gradcam_plus_plus" | "eigencam"


class ExplainRolloutInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_digest: str = Field(min_length=1)
    model_card: str
    target_class: int = Field(default=0, ge=0)
    output_size: tuple[int, int] | None = None
    head_fusion: str = "mean"
    discard_ratio: float = Field(default=0.0, ge=0.0, lt=1.0)
    has_cls_token: bool = True


class ExplainIntegratedGradientsInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_digest: str = Field(min_length=1)
    model_card: str
    target_class: int = Field(ge=0)
    steps: int = Field(default=32, ge=1)
    output_size: tuple[int, int] | None = None


# --------------------------------------------------------------------------- #
# Node implementations
# --------------------------------------------------------------------------- #


def _finalise_heatmap(  # pragma: no cover - torch only
    *,
    explainer: str,
    model_card: str,
    target_class: int,
    tile_shape: tuple[int, int, int],
    heatmap: Any,
    tile_rgb: Any | None,
) -> HeatmapArtifact:
    import numpy as np

    heatmap_arr = np.asarray(heatmap, dtype=np.float32)
    heatmap_u8 = (np.clip(heatmap_arr, 0.0, 1.0) * 255).astype(np.uint8)
    heatmap_png = encode_png(heatmap_u8)
    overlay_png: str | None = None
    if tile_rgb is not None:
        rgb = np.asarray(tile_rgb, dtype=np.uint8)
        if rgb.shape[:2] == heatmap_arr.shape:
            overlay = overlay_on_tile(rgb, heatmap_arr)
            overlay_png = encode_png(overlay)
    heatmap_shape = (int(heatmap_arr.shape[0]), int(heatmap_arr.shape[1]))
    return HeatmapArtifact(
        explainer=explainer,  # type: ignore[arg-type]
        model_card=model_card,
        target_class=target_class,
        tile_shape=tile_shape,
        heatmap_shape=heatmap_shape,
        heatmap_png=heatmap_png,
        overlay_png=overlay_png,
    )


@node(
    id="explain.gradcam",
    label="Grad-CAM / Grad-CAM++ / EigenCAM",
    tooltip=(
        "Produces a class-discriminative heatmap for a CNN classifier. "
        "Supports gradcam, gradcam_plus_plus, and eigencam kinds."
    ),
    citation=(
        "Selvaraju et al. 2017 (Grad-CAM); Chattopadhay et al. 2018 "
        "(Grad-CAM++); Muhammad & Yeasin 2020 (EigenCAM)."
    ),
)
def explain_gradcam(cfg: ExplainGradCAMInput) -> HeatmapArtifact:  # pragma: no cover - torch only
    from openpathai.explain.gradcam import (
        EigenCAM,
        GradCAM,
        GradCAMPlusPlus,
    )

    target = lookup_explain_target(cfg.target_digest)
    if target.target_layer is None:
        raise ValueError("Grad-CAM requires a target_layer on the registered target.")

    if cfg.kind == "gradcam":
        explainer = GradCAM(target.model, target.target_layer)
    elif cfg.kind == "gradcam_plus_plus":
        explainer = GradCAMPlusPlus(target.model, target.target_layer)
    elif cfg.kind == "eigencam":
        explainer = EigenCAM(target.model, target.target_layer)
    else:
        raise ValueError(f"Unknown Grad-CAM kind {cfg.kind!r}")

    heatmap = explainer.explain(
        target.tile,
        cfg.target_class,
        output_size=cfg.output_size,
    )
    tile_shape = tuple(target.tile.shape[-3:]) if target.tile.ndim >= 3 else (0, 0, 0)
    return _finalise_heatmap(
        explainer=cfg.kind,
        model_card=cfg.model_card,
        target_class=cfg.target_class,
        tile_shape=tile_shape,  # type: ignore[arg-type]
        heatmap=heatmap,
        tile_rgb=target.tile_rgb,
    )


@node(
    id="explain.attention_rollout",
    label="Attention rollout (ViT)",
    tooltip="Computes Abnar & Zuidema 2020 attention rollout for a ViT-style model.",
    citation="Abnar & Zuidema 2020, 'Quantifying Attention Flow in Transformers'.",
)
def explain_attention_rollout(  # pragma: no cover - torch only
    cfg: ExplainRolloutInput,
) -> HeatmapArtifact:
    from openpathai.explain.attention_rollout import attention_rollout

    target = lookup_explain_target(cfg.target_digest)
    heatmap = attention_rollout(
        target.model,
        target.tile,
        head_fusion=cfg.head_fusion,
        discard_ratio=cfg.discard_ratio,
        has_cls_token=cfg.has_cls_token,
        output_size=cfg.output_size,
    )
    tile_shape = tuple(target.tile.shape[-3:]) if target.tile.ndim >= 3 else (0, 0, 0)
    return _finalise_heatmap(
        explainer="attention_rollout",
        model_card=cfg.model_card,
        target_class=cfg.target_class,
        tile_shape=tile_shape,  # type: ignore[arg-type]
        heatmap=heatmap,
        tile_rgb=target.tile_rgb,
    )


@node(
    id="explain.integrated_gradients",
    label="Integrated Gradients",
    tooltip="Axiomatic per-pixel attribution via baseline-to-input path integral.",
    citation="Sundararajan et al. 2017, 'Axiomatic Attribution for Deep Networks'.",
)
def explain_integrated_gradients(  # pragma: no cover - torch only
    cfg: ExplainIntegratedGradientsInput,
) -> HeatmapArtifact:
    from openpathai.explain.integrated_gradients import integrated_gradients

    target = lookup_explain_target(cfg.target_digest)
    heatmap = integrated_gradients(
        target.model,
        target.tile,
        cfg.target_class,
        steps=cfg.steps,
        output_size=cfg.output_size,
    )
    tile_shape = tuple(target.tile.shape[-3:]) if target.tile.ndim >= 3 else (0, 0, 0)
    return _finalise_heatmap(
        explainer="integrated_gradients",
        model_card=cfg.model_card,
        target_class=cfg.target_class,
        tile_shape=tile_shape,  # type: ignore[arg-type]
        heatmap=heatmap,
        tile_rgb=target.tile_rgb,
    )
