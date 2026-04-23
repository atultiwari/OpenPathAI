"""Pipeline-facing training node.

Registers ``training.train`` with the :data:`openpathai.pipeline.REGISTRY`
so a supervised run becomes just another :class:`openpathai.pipeline.Pipeline`
step. Caching keys pick up the full :class:`TrainingConfig` + a stable
hash of the training + validation batches.

Real cohort-backed training arrives in Phase 5 when the CLI driver
wires Phase 2's data layer into this node. Phase 3 only exercises the
in-memory path via :class:`openpathai.training.datasets.InMemoryTileBatch`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from openpathai.models import default_model_registry
from openpathai.pipeline.node import node
from openpathai.pipeline.schema import canonical_sha256
from openpathai.training.artifacts import TrainingReportArtifact
from openpathai.training.config import TrainingConfig
from openpathai.training.datasets import InMemoryTileBatch
from openpathai.training.engine import LightningTrainer

__all__ = [
    "TrainingNodeInput",
    "hash_batch",
    "train",
]


def hash_batch(batch: InMemoryTileBatch) -> str:
    """Deterministic SHA-256 of a tile batch.

    Hashing the raw bytes ensures the content-addressable cache picks up
    even single-pixel differences. Separated so callers can embed the
    hash in cache keys without re-pickling the batch itself.
    """
    parts = [
        batch.pixels.shape,
        batch.pixels.dtype.str,
        batch.labels.dtype.str,
        batch.class_names,
    ]
    payload = canonical_sha256(parts)
    prefix = payload.encode("utf-8")
    pixels = batch.pixels.tobytes()
    labels = batch.labels.astype(np.int64).tobytes()
    return canonical_sha256([payload, len(prefix), _sha256_hex(pixels), _sha256_hex(labels)])


def _sha256_hex(blob: bytes) -> str:
    import hashlib

    return hashlib.sha256(blob).hexdigest()


class TrainingNodeInput(BaseModel):
    """Input schema for the ``training.train`` node.

    The batches are passed by hash so pydantic validation is cheap and
    the pipeline cache key is stable across process restarts; the caller
    is responsible for registering the actual tensors via
    :meth:`register_batches` before invoking the node.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: TrainingConfig
    train_batch_hash: str = Field(min_length=1)
    val_batch_hash: str | None = None
    checkpoint_dir: str | None = None


# A tiny module-level store so test callers can pass batches without
# re-inventing their own caching. Swap for a proper artifact store in
# Phase 5.
_BATCH_STORE: dict[str, InMemoryTileBatch] = {}


def register_batch(batch: InMemoryTileBatch) -> str:
    """Register a batch and return the hash used to look it up."""
    digest = hash_batch(batch)
    _BATCH_STORE[digest] = batch
    return digest


def lookup_batch(digest: str) -> InMemoryTileBatch:
    try:
        return _BATCH_STORE[digest]
    except KeyError as exc:
        raise KeyError(
            f"No tile batch registered for hash {digest!r}. Call "
            f"openpathai.training.node.register_batch(...) first."
        ) from exc


def clear_batches() -> None:
    """Drop every registered batch (test isolation helper)."""
    _BATCH_STORE.clear()


@node(
    id="training.train",
    label="Supervised tile classifier trainer",
    tooltip=(
        "Trains a Tier-A tile classifier with CE/Focal/LDAM losses and "
        "temperature-scaling calibration. Returns a TrainingReportArtifact."
    ),
    citation="Guo et al. 2017 (temperature scaling); Cao et al. 2019 (LDAM).",
)
def train(cfg: TrainingNodeInput) -> TrainingReportArtifact:
    registry = default_model_registry()
    card = registry.get(cfg.config.model_card)
    train_batch = lookup_batch(cfg.train_batch_hash)
    val_batch = lookup_batch(cfg.val_batch_hash) if cfg.val_batch_hash else None
    trainer = LightningTrainer(
        cfg.config,
        card=card,
        checkpoint_dir=Path(cfg.checkpoint_dir) if cfg.checkpoint_dir else None,
    )
    return trainer.fit(train=train_batch, val=val_batch)
