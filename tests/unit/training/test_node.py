"""Unit tests for the training pipeline node (no torch required)."""

from __future__ import annotations

import pytest

from openpathai.pipeline.node import REGISTRY
from openpathai.training import (
    TrainingReportArtifact,
    clear_batches,
    hash_batch,
    lookup_batch,
    register_batch,
    synthetic_tile_batch,
)


@pytest.fixture(autouse=True)
def _clean() -> None:
    clear_batches()
    yield
    clear_batches()


def test_hash_batch_is_deterministic() -> None:
    batch = synthetic_tile_batch(num_classes=3, samples_per_class=4, seed=0)
    assert hash_batch(batch) == hash_batch(batch)


def test_hash_batch_changes_with_seed() -> None:
    a = synthetic_tile_batch(num_classes=3, samples_per_class=4, seed=0)
    b = synthetic_tile_batch(num_classes=3, samples_per_class=4, seed=1)
    assert hash_batch(a) != hash_batch(b)


def test_register_and_lookup_roundtrip() -> None:
    batch = synthetic_tile_batch(num_classes=4, samples_per_class=2, seed=3)
    digest = register_batch(batch)
    assert lookup_batch(digest) is batch


def test_lookup_missing_digest_raises() -> None:
    with pytest.raises(KeyError):
        lookup_batch("does-not-exist")


def test_training_node_is_registered() -> None:
    assert REGISTRY.has("training.train")
    node_def = REGISTRY.get("training.train")
    assert node_def.output_type is TrainingReportArtifact
