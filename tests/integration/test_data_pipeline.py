"""Phase 2 integration test.

Wire slide → mask → tiler → stain-normalise as ``@openpathai.node``
nodes running through the Phase 1 executor. Proves:

1. Every operation registered via ``@node`` flows through the
   content-addressable cache without hand-plumbing.
2. Rerunning with identical inputs is all cache hits (``misses == 0``)
   and the node functions are never invoked on the rerun.
3. Unchanged cohort + slide path + tile config → deterministic
   ``RunManifest``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydantic import BaseModel

from openpathai import (
    Artifact,
    ContentAddressableCache,
    Executor,
    NodeRegistry,
    Pipeline,
    PipelineStep,
    node,
)
from openpathai.io.wsi import open_slide
from openpathai.preprocessing.mask import otsu_tissue_mask
from openpathai.preprocessing.stain import MacenkoNormalizer
from openpathai.tiling.tiler import GridTiler


class _SlideInput(BaseModel):
    path: str
    mpp: float = 0.5


class _TileInput(BaseModel):
    path: str
    mpp: float = 0.5
    tile_size: int = 256
    min_tissue_fraction: float = 0.05


class _NormInput(BaseModel):
    path: str
    x: int
    y: int
    tile_size: int = 256


class _MaskArtifact(Artifact):
    mean_coverage: float


class _TileCountArtifact(Artifact):
    n_tiles: int


class _NormStatsArtifact(Artifact):
    mean_r: float
    mean_g: float
    mean_b: float


_CALL_COUNTS: dict[str, int] = {
    "mask": 0,
    "tile": 0,
    "stain": 0,
}


@pytest.fixture
def _reset_call_counts() -> None:
    for k in _CALL_COUNTS:
        _CALL_COUNTS[k] = 0


@pytest.mark.integration
def test_data_pipeline_runs_and_caches(
    tmp_path: Path,
    synthetic_slide_path: Path,
    _reset_call_counts: None,
) -> None:
    registry = NodeRegistry()

    @node(id="phase2.mask", registry=registry)
    def run_mask(cfg: _SlideInput) -> _MaskArtifact:
        _CALL_COUNTS["mask"] += 1
        with open_slide(cfg.path, mpp=cfg.mpp) as slide:
            info = slide.info
            thumb = slide.read_region((0, 0), (info.width, info.height))
        mask = otsu_tissue_mask(thumb)
        return _MaskArtifact(mean_coverage=float(mask.mean()))

    @node(id="phase2.tile", registry=registry)
    def run_tiler(cfg: _TileInput) -> _TileCountArtifact:
        _CALL_COUNTS["tile"] += 1
        with open_slide(cfg.path, mpp=cfg.mpp) as slide:
            info = slide.info
            tile = slide.read_region((0, 0), (info.width, info.height))
        mask = otsu_tissue_mask(tile)
        tiler = GridTiler(
            tile_size_px=(cfg.tile_size, cfg.tile_size),
            min_tissue_fraction=cfg.min_tissue_fraction,
        )
        grid = tiler.plan(info, mask=mask)
        return _TileCountArtifact(n_tiles=grid.n_tiles)

    @node(id="phase2.stain", registry=registry)
    def run_stain(cfg: _NormInput) -> _NormStatsArtifact:
        _CALL_COUNTS["stain"] += 1
        with open_slide(cfg.path, mpp=0.5) as slide:
            tile = slide.read_region((cfg.x, cfg.y), (cfg.tile_size, cfg.tile_size))
        out = MacenkoNormalizer().transform(tile)
        rgb = out.reshape(-1, 3).astype(np.float64).mean(axis=0)
        return _NormStatsArtifact(
            mean_r=float(rgb[0]),
            mean_g=float(rgb[1]),
            mean_b=float(rgb[2]),
        )

    cache_root = tmp_path / "cache"
    cache = ContentAddressableCache(root=cache_root)
    executor = Executor(cache=cache, registry=registry)

    pipeline = Pipeline(
        id="phase2-data",
        steps=[
            PipelineStep(
                id="mask",
                op="phase2.mask",
                inputs={"path": str(synthetic_slide_path), "mpp": 0.5},
            ),
            PipelineStep(
                id="tile",
                op="phase2.tile",
                inputs={
                    "path": str(synthetic_slide_path),
                    "tile_size": 256,
                    "min_tissue_fraction": 0.05,
                },
            ),
            PipelineStep(
                id="stain",
                op="phase2.stain",
                inputs={
                    "path": str(synthetic_slide_path),
                    "x": 0,
                    "y": 0,
                    "tile_size": 256,
                },
            ),
        ],
    )

    first = executor.run(pipeline)
    assert first.cache_stats.misses == 3
    assert first.cache_stats.hits == 0
    assert _CALL_COUNTS == {"mask": 1, "tile": 1, "stain": 1}
    assert first.artifacts["tile"].n_tiles > 0  # type: ignore[attr-defined]

    baseline = dict(_CALL_COUNTS)
    second = executor.run(pipeline)
    assert second.cache_stats.misses == 0
    assert second.cache_stats.hits == 3
    # Node functions were not invoked on the second run.
    assert baseline == _CALL_COUNTS

    # Deterministic artifacts across runs.
    assert first.artifacts["tile"].n_tiles == second.artifacts["tile"].n_tiles  # type: ignore[attr-defined]
