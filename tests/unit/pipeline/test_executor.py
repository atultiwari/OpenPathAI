"""Unit tests for ``openpathai.pipeline.executor``."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from openpathai.pipeline.cache import ContentAddressableCache
from openpathai.pipeline.executor import (
    Executor,
    Pipeline,
    PipelineStep,
)
from openpathai.pipeline.node import NodeRegistry, node
from openpathai.pipeline.schema import Artifact, IntArtifact


class PairInput(BaseModel):
    a: int
    b: int


class ValueInput(BaseModel):
    value: int


class PairArtifact(Artifact):
    """Local artifact type used by the whole-object-reference test."""

    a: int
    b: int


class BothInput(BaseModel):
    """Input type used by the whole-object-reference test.

    Must live at module scope so ``typing.get_type_hints`` can resolve it
    from within the ``@node`` decorator's signature introspection.
    """

    a: int
    b: int


@pytest.fixture
def registry() -> NodeRegistry:
    reg = NodeRegistry()

    @node(id="ex.constant", registry=reg)
    def constant(cfg: ValueInput) -> IntArtifact:
        return IntArtifact(value=cfg.value)

    @node(id="ex.add", registry=reg)
    def add(cfg: PairInput) -> IntArtifact:
        return IntArtifact(value=cfg.a + cfg.b)

    return reg


@pytest.fixture
def executor(registry: NodeRegistry, tmp_path: Path) -> Executor:
    cache = ContentAddressableCache(root=tmp_path / "cache")
    return Executor(cache, registry=registry)


@pytest.mark.unit
def test_duplicate_step_id_rejected() -> None:
    with pytest.raises(ValidationError):
        Pipeline(
            id="p",
            steps=[
                PipelineStep(id="a", op="ex.constant", inputs={"value": 1}),
                PipelineStep(id="a", op="ex.constant", inputs={"value": 2}),
            ],
        )


@pytest.mark.unit
def test_unknown_op_rejected(executor: Executor) -> None:
    pipeline = Pipeline(
        id="p",
        steps=[PipelineStep(id="a", op="does.not.exist")],
    )
    with pytest.raises(KeyError, match="unknown op"):
        executor.run(pipeline)


@pytest.mark.unit
def test_reference_to_unknown_step_rejected(executor: Executor) -> None:
    pipeline = Pipeline(
        id="p",
        steps=[
            PipelineStep(id="a", op="ex.constant", inputs={"value": "@ghost.field"}),
        ],
    )
    with pytest.raises(ValueError, match="unknown step"):
        executor.run(pipeline)


@pytest.mark.unit
def test_self_reference_rejected(executor: Executor) -> None:
    pipeline = Pipeline(
        id="p",
        steps=[
            PipelineStep(id="a", op="ex.constant", inputs={"value": "@a.value"}),
        ],
    )
    with pytest.raises(ValueError, match="cannot reference itself"):
        executor.run(pipeline)


@pytest.mark.unit
def test_topological_order_runs_dependencies_first(executor: Executor) -> None:
    pipeline = Pipeline(
        id="p",
        # Define 'sum' before its dependencies in the list; topo sort
        # must still run 'a' and 'b' before 'sum'.
        steps=[
            PipelineStep(
                id="sum",
                op="ex.add",
                inputs={"a": "@a.value", "b": "@b.value"},
            ),
            PipelineStep(id="a", op="ex.constant", inputs={"value": 3}),
            PipelineStep(id="b", op="ex.constant", inputs={"value": 4}),
        ],
    )
    result = executor.run(pipeline)
    assert result.artifacts["sum"].value == 7
    ordered_ids = [rec.step_id for rec in result.step_records]
    assert ordered_ids.index("a") < ordered_ids.index("sum")
    assert ordered_ids.index("b") < ordered_ids.index("sum")


@pytest.mark.unit
def test_rerun_is_all_hits(executor: Executor) -> None:
    pipeline = Pipeline(
        id="p",
        steps=[
            PipelineStep(id="a", op="ex.constant", inputs={"value": 5}),
            PipelineStep(id="b", op="ex.constant", inputs={"value": 6}),
            PipelineStep(
                id="c",
                op="ex.add",
                inputs={"a": "@a.value", "b": "@b.value"},
            ),
        ],
    )
    first = executor.run(pipeline)
    assert first.cache_stats.misses == 3 and first.cache_stats.hits == 0

    second = executor.run(pipeline)
    assert second.cache_stats.hits == 3 and second.cache_stats.misses == 0
    for rec in second.step_records:
        assert rec.cache_hit is True


@pytest.mark.unit
def test_changing_a_literal_input_invalidates_downstream(
    executor: Executor,
) -> None:
    def build(c_value_shift: int) -> Pipeline:
        return Pipeline(
            id="p",
            steps=[
                PipelineStep(id="a", op="ex.constant", inputs={"value": 5}),
                PipelineStep(
                    id="b",
                    op="ex.constant",
                    inputs={"value": 6 + c_value_shift},
                ),
                PipelineStep(
                    id="c",
                    op="ex.add",
                    inputs={"a": "@a.value", "b": "@b.value"},
                ),
            ],
        )

    first = executor.run(build(0))
    assert first.cache_stats.misses == 3

    # Change `b`'s literal. `a` should still hit; `b` and `c` miss.
    second = executor.run(build(1))
    by_step = {rec.step_id: rec for rec in second.step_records}
    assert by_step["a"].cache_hit is True
    assert by_step["b"].cache_hit is False
    assert by_step["c"].cache_hit is False
    assert second.artifacts["c"].value == 5 + 7


@pytest.mark.unit
def test_whole_object_reference_resolves_to_model_dump(
    registry: NodeRegistry, tmp_path: Path
) -> None:
    """``@step`` (no field) passes the whole upstream artifact as a dict."""

    @node(id="ex.passthrough", registry=registry)
    def passthrough(cfg: PairInput) -> IntArtifact:
        return IntArtifact(value=cfg.a + cfg.b)

    @node(id="ex.pair", registry=registry)
    def make_pair(cfg: BothInput) -> PairArtifact:
        return PairArtifact(a=cfg.a, b=cfg.b)

    cache = ContentAddressableCache(root=tmp_path / "cache")
    executor = Executor(cache, registry=registry)

    pipeline = Pipeline(
        id="p",
        steps=[
            PipelineStep(id="pair", op="ex.pair", inputs={"a": 2, "b": 3}),
            PipelineStep(id="sum", op="ex.passthrough", inputs={"a": "@pair.a", "b": "@pair.b"}),
        ],
    )
    result = executor.run(pipeline)
    assert result.artifacts["sum"].value == 5
