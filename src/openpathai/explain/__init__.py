"""Explainability — Grad-CAM family + attention rollout + IG.

Public API:

* :class:`HeatmapArtifact` — pydantic artifact wrapping a PNG heatmap
  with enough provenance to hash into the pipeline cache.
* :class:`GradCAM`, :class:`GradCAMPlusPlus`, :class:`EigenCAM` —
  CNN explainers driven by forward/backward hooks.
* :class:`AttentionRollout` / :func:`attention_rollout` — ViT
  explainer (Abnar & Zuidema 2020).
* :func:`integrated_gradients` — axiomatic attribution
  (Sundararajan et al. 2017).
* :class:`SlideHeatmapGrid` + :class:`TilePlacement` — slide-level
  stitching stub; Phase 9 promotes it to a full DZI path.
* utility helpers :func:`normalise_01`, :func:`resize_heatmap`,
  :func:`overlay_on_tile`, :func:`encode_png`, :func:`decode_png`.
"""

from __future__ import annotations

from openpathai.explain.artifacts import HeatmapArtifact
from openpathai.explain.attention_rollout import (
    AttentionRollout,
    attention_rollout,
    rollout_from_matrices,
)
from openpathai.explain.base import (
    decode_png,
    encode_png,
    heatmap_to_rgb,
    normalise_01,
    overlay_on_tile,
    resize_heatmap,
)
from openpathai.explain.gradcam import (
    EigenCAM,
    GradCAM,
    GradCAMPlusPlus,
    eigencam_from_activation,
    resolve_layer,
)
from openpathai.explain.integrated_gradients import integrated_gradients
from openpathai.explain.node import (
    ExplainGradCAMInput,
    ExplainIntegratedGradientsInput,
    ExplainRolloutInput,
    clear_explain_targets,
    lookup_explain_target,
    register_explain_target,
)
from openpathai.explain.slide_aggregator import (
    SlideHeatmapGrid,
    TilePlacement,
)

__all__ = [
    "AttentionRollout",
    "EigenCAM",
    "ExplainGradCAMInput",
    "ExplainIntegratedGradientsInput",
    "ExplainRolloutInput",
    "GradCAM",
    "GradCAMPlusPlus",
    "HeatmapArtifact",
    "SlideHeatmapGrid",
    "TilePlacement",
    "attention_rollout",
    "clear_explain_targets",
    "decode_png",
    "eigencam_from_activation",
    "encode_png",
    "heatmap_to_rgb",
    "integrated_gradients",
    "lookup_explain_target",
    "normalise_01",
    "overlay_on_tile",
    "register_explain_target",
    "resize_heatmap",
    "resolve_layer",
    "rollout_from_matrices",
]
