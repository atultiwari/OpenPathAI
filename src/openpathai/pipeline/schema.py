"""Typed artifact schema — the ``Artifact`` base class every pipeline node
consumes and produces.

Phase 1 ships only the base class plus a handful of toy scalar artifacts
used in the primitive-layer tests. Pathology-specific artifacts
(``MaskedSlideArtifact``, ``TileSetArtifact``, ``EmbeddingTableArtifact``,
``MaskArtifact``, ``BoundingBoxArtifact``, ...) arrive in Phase 2's
``openpathai.io`` and Phase 14's detection/segmentation layer.

Deterministic hashing contract
------------------------------
``Artifact.content_hash()`` computes a SHA-256 over the **canonical JSON**
representation of the artifact's fields. Canonical JSON here means:

* `sort_keys=True` — field insertion order does not affect the hash.
* `separators=(",", ":")` — no incidental whitespace contributes to the
  hash.
* `default=str` — fall back to ``str()`` for non-JSON-primitive values so
  that ``Path``, ``datetime``, etc. hash stably.

The hash is part of Bet 3 (reproducibility as architecture): every
downstream consumer of an artifact embeds its content hash in its own
cache key, so a change to any upstream value invalidates every affected
downstream step.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict

__all__ = [
    "Artifact",
    "FloatArtifact",
    "IntArtifact",
    "ScalarArtifact",
    "StringArtifact",
    "canonical_json",
    "canonical_sha256",
]


def canonical_json(value: Any) -> str:
    """Serialise ``value`` to a deterministic JSON string.

    Used by both artifact hashing and cache-key construction so the two
    agree byte-for-byte.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def canonical_sha256(value: Any) -> str:
    """Deterministic SHA-256 hex digest of ``value`` serialised via
    :func:`canonical_json`.
    """
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class Artifact(BaseModel):
    """Base class for every typed pipeline artifact.

    Subclasses declare their data as pydantic fields. The
    :meth:`content_hash` method provides a deterministic identity that
    downstream cache keys can depend on.
    """

    model_config = ConfigDict(
        # Immutability keeps artifacts safe to share across steps.
        frozen=True,
        # Artifacts are dataclass-like; forbid extras for clarity.
        extra="forbid",
    )

    @property
    def artifact_type(self) -> str:
        """Return the artifact class name (used in manifests and registries)."""
        return type(self).__name__

    def content_hash(self) -> str:
        """Deterministic SHA-256 over the artifact's canonical JSON form.

        Field insertion order does not affect the hash (see module
        docstring for the canonicalisation rules).
        """
        payload = {
            "artifact_type": self.artifact_type,
            "fields": self.model_dump(mode="json"),
        }
        return canonical_sha256(payload)


# ─── Toy built-in artifacts (used in Phase 1 tests only) ──────────────────


class ScalarArtifact(Artifact):
    """Abstract marker — scalar-value artifact for toy pipelines."""


class IntArtifact(ScalarArtifact):
    """Holds a single integer."""

    value: int


class FloatArtifact(ScalarArtifact):
    """Holds a single float."""

    value: float


class StringArtifact(ScalarArtifact):
    """Holds a single string."""

    value: str
