"""Phase 10 — reference pipeline ``supervised_tile_classification.yaml``."""

from __future__ import annotations

from pathlib import Path

from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.pipeline import ContentAddressableCache, Executor


def test_reference_pipeline_loads_and_validates() -> None:
    path = Path(__file__).resolve().parents[2] / "pipelines" / "supervised_tile_classification.yaml"
    pipeline = load_pipeline(path)
    assert pipeline.id == "supervised-tile-classification"
    assert pipeline.cohort_fanout == "load_slide_index"
    assert pipeline.max_workers == 4


def test_reference_pipeline_runs(tmp_path: Path) -> None:
    path = Path(__file__).resolve().parents[2] / "pipelines" / "supervised_tile_classification.yaml"
    pipeline = load_pipeline(path)
    cache = ContentAddressableCache(root=tmp_path / "cache")

    first = Executor(cache, max_workers=4, parallel_mode="thread").run(pipeline)
    second = Executor(cache, max_workers=4, parallel_mode="thread").run(pipeline)

    assert first.cache_stats.misses == len(pipeline.steps)
    assert second.cache_stats.hits == len(pipeline.steps)
    assert second.cache_stats.misses == 0
