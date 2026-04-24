"""Phase 10 — threaded executor produces the same manifest as sequential."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.pipeline import ContentAddressableCache, Executor


def _pipeline_path() -> Path:
    return Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"


def test_threaded_mode_matches_sequential(tmp_path: Path) -> None:
    pipeline = load_pipeline(_pipeline_path())
    cache_a = ContentAddressableCache(root=tmp_path / "a")
    cache_b = ContentAddressableCache(root=tmp_path / "b")

    seq = Executor(cache_a).run(pipeline)
    par = Executor(cache_b, max_workers=4, parallel_mode="thread").run(pipeline)

    assert seq.manifest.pipeline_graph_hash == par.manifest.pipeline_graph_hash
    assert seq.cache_stats.hits == par.cache_stats.hits == 0
    assert seq.cache_stats.misses == par.cache_stats.misses == len(pipeline.steps)
    # Manifest step order should be identical (topo-preserving).
    assert [s.step_id for s in seq.manifest.steps] == [s.step_id for s in par.manifest.steps]


def test_second_run_hits_cache(tmp_path: Path) -> None:
    pipeline = load_pipeline(_pipeline_path())
    cache = ContentAddressableCache(root=tmp_path / "c")
    executor = Executor(cache, max_workers=4, parallel_mode="thread")
    first = executor.run(pipeline)
    second = executor.run(pipeline)
    assert first.cache_stats.misses == len(pipeline.steps)
    assert second.cache_stats.hits == len(pipeline.steps)
    assert second.cache_stats.misses == 0


def test_invalid_parallel_mode_rejected(tmp_path: Path) -> None:
    cache = ContentAddressableCache(root=tmp_path / "c")
    with pytest.raises(ValueError, match="parallel_mode"):
        Executor(cache, parallel_mode="distributed")  # type: ignore[arg-type]


def test_invalid_max_workers_rejected(tmp_path: Path) -> None:
    cache = ContentAddressableCache(root=tmp_path / "c")
    with pytest.raises(ValueError, match="max_workers"):
        Executor(cache, max_workers=0)


def test_cache_race_safety(tmp_path: Path) -> None:
    """Two threads writing the same cache key must both complete."""
    from openpathai.pipeline.schema import IntArtifact

    cache = ContentAddressableCache(root=tmp_path / "race")
    key = ContentAddressableCache.key(
        node_id="race_test",
        code_hash="x" * 64,
        input_config={"v": 1},
        upstream_hashes=[],
    )
    errors: list[Exception] = []

    def worker() -> None:
        try:
            artifact = IntArtifact(value=42)
            cache.put(
                key,
                node_id="race_test",
                code_hash="x" * 64,
                input_config={"v": 1},
                upstream_hashes=[],
                artifact=artifact,
            )
        except Exception as exc:  # pragma: no cover - failing branch
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"cache writes raced: {errors!r}"
    # Final artifact must be the correct value (either write wins identically).
    loaded = cache.get(key, IntArtifact)
    assert loaded is not None
    assert loaded.value == 42
