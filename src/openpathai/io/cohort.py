"""Cohort abstraction — typed, hashable groups of slide references.

Pipelines take cohorts, not individual slides (master-plan §9.4). The
``Cohort`` itself is a pydantic frozen model so it inherits
``Artifact``-style deterministic hashing, which makes the executor's
content-addressable cache work naturally at cohort scope.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import PureWindowsPath
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
        """Normalise a filesystem path in a cross-platform way.

        The Phase 2 contract is "collapse repeated separators without
        otherwise touching the path shape". ``pathlib.Path`` is
        OS-dependent (PosixPath on macOS/Linux, WindowsPath on
        Windows) and would rewrite ``/tmp/slide.svs`` to
        ``\\tmp\\slide.svs`` on Windows, which is wrong for slide
        paths that routinely come from URIs / POSIX cohorts.
        """
        # Keep URIs as-is; only normalise pure filesystem paths.
        if "://" in value:
            return value
        # Pure Windows paths (drive letter, or containing ``\``) are
        # normalised through ``PureWindowsPath`` so ``C:\\foo\\\\bar``
        # collapses correctly.
        if re.match(r"^[A-Za-z]:[\\/]", value) or "\\" in value:
            return str(PureWindowsPath(value))
        # Everything else is treated as POSIX-style: collapse any run
        # of forward slashes to a single slash. This is deliberately
        # OS-agnostic — the path remains a verbatim string that the
        # Phase 2 SlideReader interprets.
        collapsed = re.sub(r"/+", "/", value)
        # Preserve the historical trailing-slash semantics of
        # ``str(PurePosixPath(...))``: a bare "/" stays as "/", any
        # non-root path drops a trailing separator.
        if len(collapsed) > 1 and collapsed.endswith("/"):
            collapsed = collapsed.rstrip("/") or "/"
        return collapsed

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
