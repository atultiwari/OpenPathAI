"""Pipeline artifacts produced by the explainability layer."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from openpathai.pipeline.schema import Artifact

__all__ = ["HeatmapArtifact"]


ExplainerKind = Literal[
    "gradcam",
    "gradcam_plus_plus",
    "eigencam",
    "attention_rollout",
    "integrated_gradients",
]
"""Every explainer shipped in Phase 4 registers under one of these."""


class HeatmapArtifact(Artifact):
    """A single heatmap on a single tile.

    The heatmap pixels live in ``heatmap_png`` as a base64-encoded PNG
    so the artifact serialises cleanly through the pipeline cache and
    the run manifest. Raw float arrays are recoverable via
    :func:`openpathai.explain.base.decode_png`.
    """

    explainer: ExplainerKind
    model_card: str
    target_class: int
    tile_shape: tuple[int, int, int]  # (H, W, C)
    heatmap_shape: tuple[int, int]  # (H, W)
    heatmap_png: str = Field(min_length=1)
    overlay_png: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)
