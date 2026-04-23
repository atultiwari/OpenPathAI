"""Unit tests for HeatmapArtifact."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from openpathai.explain.artifacts import HeatmapArtifact
from openpathai.explain.base import encode_png


def _heatmap_blob() -> str:
    rng = np.random.default_rng(0)
    return encode_png(rng.integers(0, 256, size=(8, 8), dtype=np.uint8))


def test_heatmap_artifact_round_trip() -> None:
    art = HeatmapArtifact(
        explainer="gradcam",
        model_card="resnet18",
        target_class=1,
        tile_shape=(3, 16, 16),
        heatmap_shape=(8, 8),
        heatmap_png=_heatmap_blob(),
    )
    raw = art.model_dump_json()
    art2 = HeatmapArtifact.model_validate_json(raw)
    assert art == art2
    assert art.content_hash() == art2.content_hash()


def test_heatmap_artifact_hash_ignores_declaration_order() -> None:
    blob = _heatmap_blob()
    a = HeatmapArtifact(
        explainer="gradcam",
        model_card="resnet18",
        target_class=1,
        tile_shape=(3, 16, 16),
        heatmap_shape=(8, 8),
        heatmap_png=blob,
    )
    b = HeatmapArtifact(
        explainer="gradcam",
        heatmap_png=blob,
        target_class=1,
        model_card="resnet18",
        heatmap_shape=(8, 8),
        tile_shape=(3, 16, 16),
    )
    assert a.content_hash() == b.content_hash()


def test_heatmap_artifact_rejects_empty_png() -> None:
    with pytest.raises(ValidationError):
        HeatmapArtifact(
            explainer="gradcam",
            model_card="resnet18",
            target_class=0,
            tile_shape=(3, 4, 4),
            heatmap_shape=(2, 2),
            heatmap_png="",
        )


def test_heatmap_artifact_rejects_unknown_explainer() -> None:
    with pytest.raises(ValidationError):
        HeatmapArtifact(
            explainer="mystery",  # type: ignore[arg-type]
            model_card="resnet18",
            target_class=0,
            tile_shape=(3, 4, 4),
            heatmap_shape=(2, 2),
            heatmap_png=_heatmap_blob(),
        )
