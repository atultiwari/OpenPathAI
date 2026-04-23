"""Unit tests for ``openpathai.pipeline.node``."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from openpathai.pipeline.node import NodeRegistry, node
from openpathai.pipeline.schema import IntArtifact


class DoubleInput(BaseModel):
    value: int


@pytest.fixture
def registry() -> NodeRegistry:
    return NodeRegistry()


@pytest.mark.unit
def test_node_decorator_registers_function(registry: NodeRegistry) -> None:
    @node(id="t.double", registry=registry)
    def double(cfg: DoubleInput) -> IntArtifact:
        return IntArtifact(value=cfg.value * 2)

    assert registry.has("t.double")
    definition = registry.get("t.double")
    assert definition.input_type is DoubleInput
    assert definition.output_type is IntArtifact
    # Function remains directly callable.
    assert double(DoubleInput(value=3)).value == 6


@pytest.mark.unit
def test_duplicate_node_id_raises(registry: NodeRegistry) -> None:
    @node(id="t.dupe", registry=registry)
    def f(cfg: DoubleInput) -> IntArtifact:
        return IntArtifact(value=cfg.value)

    assert f is not None  # silence unused-local-var

    def g(cfg: DoubleInput) -> IntArtifact:
        return IntArtifact(value=cfg.value + 1)

    with pytest.raises(ValueError, match="already registered"):
        node(id="t.dupe", registry=registry)(g)


@pytest.mark.unit
def test_re_registering_same_function_is_idempotent(registry: NodeRegistry) -> None:
    @node(id="t.same", registry=registry)
    def f(cfg: DoubleInput) -> IntArtifact:
        return IntArtifact(value=cfg.value)

    # Re-decorating the *same* function must not raise.
    node(id="t.same", registry=registry)(f)
    assert registry.has("t.same")


@pytest.mark.unit
def test_node_requires_typed_input(registry: NodeRegistry) -> None:
    with pytest.raises(TypeError, match="annotate"):

        @node(id="t.untyped", registry=registry)
        def f(cfg) -> IntArtifact:  # type: ignore[no-untyped-def]  — deliberate
            return IntArtifact(value=0)


@pytest.mark.unit
def test_node_requires_basemodel_input(registry: NodeRegistry) -> None:
    with pytest.raises(TypeError, match="pydantic BaseModel"):

        @node(id="t.intin", registry=registry)
        def f(cfg: int) -> IntArtifact:
            return IntArtifact(value=cfg)


@pytest.mark.unit
def test_node_requires_return_annotation(registry: NodeRegistry) -> None:
    with pytest.raises(TypeError, match="return type"):

        @node(id="t.noret", registry=registry)
        def f(cfg: DoubleInput):  # type: ignore[no-untyped-def]  — deliberate
            return IntArtifact(value=cfg.value)


@pytest.mark.unit
def test_node_rejects_multi_parameter_functions(registry: NodeRegistry) -> None:
    with pytest.raises(TypeError, match="exactly one parameter"):

        @node(id="t.multi", registry=registry)
        def f(cfg: DoubleInput, extra: int) -> IntArtifact:
            return IntArtifact(value=cfg.value + extra)


@pytest.mark.unit
def test_code_hash_differs_for_different_bodies(registry: NodeRegistry) -> None:
    @node(id="t.a", registry=registry)
    def fn_a(cfg: DoubleInput) -> IntArtifact:
        return IntArtifact(value=cfg.value * 2)

    @node(id="t.b", registry=registry)
    def fn_b(cfg: DoubleInput) -> IntArtifact:
        return IntArtifact(value=cfg.value * 3)

    assert registry.get("t.a").code_hash != registry.get("t.b").code_hash


@pytest.mark.unit
def test_invoke_coerces_dict_inputs(registry: NodeRegistry) -> None:
    @node(id="t.coerce", registry=registry)
    def double(cfg: DoubleInput) -> IntArtifact:
        return IntArtifact(value=cfg.value * 2)

    definition = registry.get("t.coerce")
    out = definition.invoke({"value": 5})  # type: ignore[arg-type]
    assert out.value == 10


@pytest.mark.unit
def test_registry_snapshot_restore(registry: NodeRegistry) -> None:
    snapshot = registry.snapshot()

    @node(id="t.snap", registry=registry)
    def f(cfg: DoubleInput) -> IntArtifact:
        return IntArtifact(value=cfg.value)

    assert registry.has("t.snap")
    registry.restore(snapshot)
    assert not registry.has("t.snap")
    del f
