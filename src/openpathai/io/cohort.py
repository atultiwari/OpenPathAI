"""Cohort abstraction — typed, hashable groups of slide references.

Pipelines take cohorts, not individual slides (master-plan §9.4). The
``Cohort`` itself is a pydantic frozen model so it inherits
``Artifact``-style deterministic hashing, which makes the executor's
content-addressable cache work naturally at cohort scope.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "Cohort",
    "SlideRef",
]


class SlideRef(BaseModel):
    """Pointer to a single slide (file or logical handle).

    ``path`` is opaque to the model — it can be a local path, a
    URI, or an index into an external store. Hashing of the
    enclosing :class:`Cohort` only hashes the declared fields; if the
    slide file itself changes on disk, cache invalidation is the
    responsibility of the node that reads the slide (phase-2
    :class:`~openpathai.io.wsi.SlideReader`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    slide_id: str = Field(min_length=1)
    path: str
    patient_id: str | None = None
    label: str | None = None
    mpp: float | None = Field(default=None, gt=0.0)
    magnification: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def _normalise_path(cls, value: str) -> str:
        # Keep URIs as-is; only normalise pure filesystem paths.
        if "://" in value:
            return value
        return str(Path(value))

    @property
    def is_file(self) -> bool:
        return "://" not in self.path


class Cohort(BaseModel):
    """Named, ordered group of :class:`SlideRef`.

    Equality and hashing are driven by the sorted ``slides`` tuple and
    canonical JSON of ``metadata`` — so two cohorts with the same
    slides in a different declaration order hash identically.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    slides: tuple[SlideRef, ...]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slides")
    @classmethod
    def _validate_slides(cls, value: tuple[SlideRef, ...]) -> tuple[SlideRef, ...]:
        if not value:
            raise ValueError("Cohort must contain at least one SlideRef")
        ids = [s.slide_id for s in value]
        if len(set(ids)) != len(ids):
            raise ValueError("Cohort slide_ids must be unique")
        # Canonicalise the order so two cohorts declared with different
        # iteration orders hash identically.
        return tuple(sorted(value, key=lambda s: s.slide_id))

    def content_hash(self) -> str:
        """Stable SHA-256 of the cohort (id + slides + metadata)."""
        payload = {
            "id": self.id,
            "slides": [s.model_dump() for s in self.slides],
            "metadata": self.metadata,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def patient_ids(self) -> tuple[str, ...]:
        """All distinct patient IDs (``None`` collapsed to the slide ID)."""
        out: list[str] = []
        for s in self.slides:
            out.append(s.patient_id if s.patient_id is not None else s.slide_id)
        return tuple(out)

    def by_slide_id(self, slide_id: str) -> SlideRef:
        for s in self.slides:
            if s.slide_id == slide_id:
                return s
        raise KeyError(f"slide_id {slide_id!r} not in cohort {self.id!r}")

    def __len__(self) -> int:
        return len(self.slides)
