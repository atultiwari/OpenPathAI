"""Phase 10 — ``Executor.run_cohort`` fans a pipeline over slides."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.io import Cohort, SlideRef
from openpathai.pipeline import ContentAddressableCache, Executor


def _cohort(n: int = 4) -> Cohort:
    return Cohort(
        id="fanout-test",
        slides=tuple(
            SlideRef(slide_id=f"slide-{i:02d}", path=f"/tmp/slide-{i:02d}.svs") for i in range(n)
        ),
    )


def _fanout_pipeline():
    pipeline = load_pipeline(
        Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"
    )
    return pipeline.model_copy(update={"cohort_fanout": pipeline.steps[0].id})


def test_run_cohort_produces_one_result_per_slide(tmp_path: Path) -> None:
    cache = ContentAddressableCache(root=tmp_path / "c")
    executor = Executor(cache)
    pipeline = _fanout_pipeline()
    result = executor.run_cohort(pipeline, _cohort(4))
    assert len(result.per_slide) == 4
    assert result.cohort_id == "fanout-test"


def test_run_cohort_second_pass_all_hits(tmp_path: Path) -> None:
    cache = ContentAddressableCache(root=tmp_path / "c")
    executor = Executor(cache, max_workers=4, parallel_mode="thread")
    pipeline = _fanout_pipeline()
    first = executor.run_cohort(pipeline, _cohort(4))
    second = executor.run_cohort(pipeline, _cohort(4))
    # Four slides x three steps = twelve node executions.
    assert first.cache_stats.hits + first.cache_stats.misses == 12
    assert second.cache_stats.hits == 12
    assert second.cache_stats.misses == 0


def test_run_cohort_requires_cohort_fanout(tmp_path: Path) -> None:
    cache = ContentAddressableCache(root=tmp_path / "c")
    executor = Executor(cache)
    pipeline = load_pipeline(
        Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"
    )
    with pytest.raises(ValueError, match="cohort_fanout"):
        executor.run_cohort(pipeline, _cohort(1))


def test_run_cohort_bad_fanout_id(tmp_path: Path) -> None:
    cache = ContentAddressableCache(root=tmp_path / "c")
    executor = Executor(cache)
    pipeline = load_pipeline(
        Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"
    )
    pipeline = pipeline.model_copy(update={"cohort_fanout": "does-not-exist"})
    with pytest.raises(ValueError, match="does not match any step id"):
        executor.run_cohort(pipeline, _cohort(1))


def test_per_slide_manifests_have_distinct_ids(tmp_path: Path) -> None:
    cache = ContentAddressableCache(root=tmp_path / "c")
    executor = Executor(cache)
    result = executor.run_cohort(_fanout_pipeline(), _cohort(3))
    ids = [r.manifest.run_id for r in result.per_slide]
    pipeline_ids = [r.manifest.pipeline_id for r in result.per_slide]
    assert len(set(ids)) == 3  # run_ids are uuids, always distinct
    # pipeline id is scoped per slide → unique per slide.
    assert len(set(pipeline_ids)) == 3
