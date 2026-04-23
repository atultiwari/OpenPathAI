"""End-to-end integration test for the Phase 4 explain pipeline.

Only runs when torch is installed — gated behind ``pytest.importorskip``.
Builds a tiny 2-conv CNN, registers it as an explain target, and runs
``explain.gradcam`` and ``explain.integrated_gradients`` through the
pipeline executor. Verifies caching on rerun.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

torch_missing = importlib.util.find_spec("torch") is None
pytestmark = pytest.mark.skipif(torch_missing, reason="torch not installed")


@pytest.fixture(autouse=True)
def _clean_targets() -> None:
    from openpathai.explain import clear_explain_targets

    clear_explain_targets()
    yield
    clear_explain_targets()


def test_gradcam_and_ig_pipeline_cache(tmp_path: Path) -> None:
    import torch
    import torch.nn as nn

    from openpathai.explain import (
        HeatmapArtifact,
        decode_png,
        register_explain_target,
    )
    from openpathai.pipeline import (
        ContentAddressableCache,
        Executor,
        Pipeline,
        PipelineStep,
    )

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
            return self.fc(self.pool(x).flatten(1))

    model = _Tiny()
    tile = torch.randn(1, 3, 16, 16)
    rgb = (np.random.default_rng(0).integers(0, 256, size=(16, 16, 3))).astype(np.uint8)

    digest = register_explain_target(model, tile, target_layer=model.conv2, tile_rgb=rgb)

    cache = ContentAddressableCache(root=tmp_path / "cache")
    executor = Executor(cache)
    pipeline = Pipeline(
        id="phase4-smoke",
        steps=[
            PipelineStep(
                id="cam",
                op="explain.gradcam",
                inputs={
                    "target_digest": digest,
                    "model_card": "tiny-cnn",
                    "target_class": 0,
                    "kind": "gradcam",
                    "output_size": [16, 16],
                },
            ),
            PipelineStep(
                id="ig",
                op="explain.integrated_gradients",
                inputs={
                    "target_digest": digest,
                    "model_card": "tiny-cnn",
                    "target_class": 0,
                    "steps": 4,
                    "output_size": [16, 16],
                },
            ),
        ],
    )

    result = executor.run(pipeline)
    assert result.cache_stats.misses == 2
    assert result.cache_stats.hits == 0

    cam: HeatmapArtifact = result.artifacts["cam"]  # type: ignore[assignment]
    ig: HeatmapArtifact = result.artifacts["ig"]  # type: ignore[assignment]
    assert cam.heatmap_shape == (16, 16)
    assert ig.heatmap_shape == (16, 16)
    assert cam.overlay_png is not None  # tile_rgb supplied
    assert ig.overlay_png is not None

    # Round-trip one of the heatmaps back to pixels.
    pixels = decode_png(cam.heatmap_png)
    assert pixels.shape == (16, 16)

    # Rerun with the same inputs — full cache hit.
    result2 = executor.run(pipeline)
    assert result2.cache_stats.hits == 2
    assert result2.cache_stats.misses == 0
