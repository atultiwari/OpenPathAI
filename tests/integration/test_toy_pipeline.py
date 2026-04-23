"""End-to-end integration test for the Phase 1 acceptance criterion:

> A toy 3-node pipeline (in-memory) runs, caches, reruns as no-ops.

Also verifies that the executor does not invoke node functions when every
step is a cache hit, by wrapping the node function with a spy counter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from openpathai.pipeline import (
    ContentAddressableCache,
    Executor,
    IntArtifact,
    NodeRegistry,
    Pipeline,
    PipelineStep,
    RunManifest,
    node,
)


class ValueInput(BaseModel):
    value: int


@pytest.mark.integration
def test_toy_three_node_pipeline_runs_caches_and_reruns(tmp_path: Path) -> None:
    registry = NodeRegistry()
    call_counts = {"constant": 0, "double": 0, "square": 0}

    @node(id="toy.constant", registry=registry)
    def constant(cfg: ValueInput) -> IntArtifact:
        call_counts["constant"] += 1
        return IntArtifact(value=cfg.value)

    @node(id="toy.double", registry=registry)
    def double(cfg: ValueInput) -> IntArtifact:
        call_counts["double"] += 1
        return IntArtifact(value=cfg.value * 2)

    @node(id="toy.square", registry=registry)
    def square(cfg: ValueInput) -> IntArtifact:
        call_counts["square"] += 1
        return IntArtifact(value=cfg.value * cfg.value)

    cache = ContentAddressableCache(root=tmp_path / "cache")
    executor = Executor(cache, registry=registry)

    pipeline = Pipeline(
        id="toy",
        steps=[
            PipelineStep(id="a", op="toy.constant", inputs={"value": 5}),
            PipelineStep(id="b", op="toy.double", inputs={"value": "@a.value"}),
            PipelineStep(id="c", op="toy.square", inputs={"value": "@b.value"}),
        ],
    )

    # ── First run: 3 misses, every node function invoked ────────────────
    first = executor.run(pipeline)
    assert first.cache_stats.misses == 3
    assert first.cache_stats.hits == 0
    assert call_counts == {"constant": 1, "double": 1, "square": 1}
    assert first.artifacts["a"].value == 5
    assert first.artifacts["b"].value == 10
    assert first.artifacts["c"].value == 100

    # ── Second run: 3 hits, no node function invoked ────────────────────
    second = executor.run(pipeline)
    assert second.cache_stats.hits == 3
    assert second.cache_stats.misses == 0
    # Spy counters unchanged — proves cache hits skip execution.
    assert call_counts == {"constant": 1, "double": 1, "square": 1}

    # Artifacts are byte-equivalent.
    assert second.artifacts["c"].value == 100

    # Manifest round-trips.
    reloaded = RunManifest.from_json(second.manifest.to_json())
    assert reloaded == second.manifest


@pytest.mark.integration
def test_changing_input_only_invalidates_downstream(tmp_path: Path) -> None:
    registry = NodeRegistry()

    @node(id="chain.constant", registry=registry)
    def constant(cfg: ValueInput) -> IntArtifact:
        return IntArtifact(value=cfg.value)

    @node(id="chain.double", registry=registry)
    def double(cfg: ValueInput) -> IntArtifact:
        return IntArtifact(value=cfg.value * 2)

    cache = ContentAddressableCache(root=tmp_path / "cache")
    executor = Executor(cache, registry=registry)

    def build(seed: int) -> Pipeline:
        return Pipeline(
            id="p",
            steps=[
                PipelineStep(id="a", op="chain.constant", inputs={"value": 10}),
                PipelineStep(id="b", op="chain.constant", inputs={"value": seed}),
                PipelineStep(id="c", op="chain.double", inputs={"value": "@b.value"}),
            ],
        )

    first = executor.run(build(seed=3))
    assert first.cache_stats.misses == 3

    # Change only `b`'s literal. `a` should still hit; `b` and `c` miss.
    second = executor.run(build(seed=7))
    by_step = {rec.step_id: rec for rec in second.step_records}
    assert by_step["a"].cache_hit is True
    assert by_step["b"].cache_hit is False
    assert by_step["c"].cache_hit is False
    assert second.artifacts["c"].value == 14
