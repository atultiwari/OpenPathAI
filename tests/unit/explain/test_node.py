"""Unit tests for explain node registration + target-store helpers."""

from __future__ import annotations

import pytest

from openpathai.explain import (
    HeatmapArtifact,
    clear_explain_targets,
    lookup_explain_target,
    register_explain_target,
)
from openpathai.pipeline.node import REGISTRY


@pytest.fixture(autouse=True)
def _clean_targets() -> None:
    clear_explain_targets()
    yield
    clear_explain_targets()


def test_explain_gradcam_node_is_registered() -> None:
    assert REGISTRY.has("explain.gradcam")
    node_def = REGISTRY.get("explain.gradcam")
    assert node_def.output_type is HeatmapArtifact


def test_explain_attention_rollout_and_ig_nodes_registered() -> None:
    assert REGISTRY.has("explain.attention_rollout")
    assert REGISTRY.has("explain.integrated_gradients")


def test_register_and_lookup_target_round_trips() -> None:
    model = object()

    class _Tile:
        shape = (3, 8, 8)
        ndim = 3

        def sum(self) -> _TileScalar:
            return _TileScalar()

    class _TileScalar:
        def item(self) -> float:
            return 0.0

    target = _Tile()
    digest = register_explain_target(model, target)
    assert lookup_explain_target(digest).model is model
    assert lookup_explain_target(digest).tile is target


def test_lookup_unknown_digest_raises() -> None:
    with pytest.raises(KeyError):
        lookup_explain_target("missing")


def test_clear_explain_targets_empties_store() -> None:
    class _Tile:
        shape = (3, 8, 8)
        ndim = 3

        def sum(self) -> _TileScalar:
            return _TileScalar()

    class _TileScalar:
        def item(self) -> float:
            return 0.0

    digest = register_explain_target(object(), _Tile())
    assert lookup_explain_target(digest) is not None
    clear_explain_targets()
    with pytest.raises(KeyError):
        lookup_explain_target(digest)
