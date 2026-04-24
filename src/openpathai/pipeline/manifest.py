"""Run manifest — the hashable receipt every pipeline run produces.

Bet 3 (reproducibility as architecture) lives here. Every executor run
emits a ``RunManifest`` that captures:

* the pipeline graph hash,
* per-step cache hits / misses + artifact hashes,
* a snapshot of the execution environment (OpenPathAI version, Python
  version, platform, Git commit).

The manifest is designed to be **diff-able** (via ``openpathai diff`` in
Phase 8) and — from Phase 17 onward — **signable** via sigstore for
Diagnostic-mode runs.

Sensitive-data policy
---------------------
The manifest records filename **hashes**, not filenames, and never
includes PHI. See the iron rules in ``CLAUDE.md`` §2.
"""

from __future__ import annotations

import platform as _platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata as _metadata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from openpathai.pipeline.schema import canonical_sha256


def _read_openpathai_version() -> str:
    """Read the installed package version, or fall back to a dev sentinel.

    Using ``importlib.metadata`` avoids a circular import back into
    ``openpathai.__init__`` during bootstrap of the pipeline primitives.
    """
    try:
        return _metadata.version("openpathai")
    except (
        _metadata.PackageNotFoundError
    ):  # pragma: no cover — running from source tree without install
        return "0.0.0+unknown"


__all__ = [
    "CacheStats",
    "Environment",
    "NodeRunRecord",
    "RunManifest",
    "capture_environment",
]


Mode = Literal["exploratory", "diagnostic"]
MANIFEST_VERSION = "1.0"


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _git_commit() -> str | None:
    """Best-effort ``git rev-parse HEAD`` of the current working tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover — no git
        return None
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit or None


def git_working_tree_status() -> tuple[bool, str]:
    """Return ``(is_clean, diagnostic_summary)`` for the current working tree.

    ``is_clean`` is ``True`` when ``git status --porcelain`` emits no rows.
    ``diagnostic_summary`` is the raw porcelain output when dirty (for
    error messages), or an empty string when clean or when no git tree
    could be found (e.g. the code is running outside a git checkout — in
    which case ``is_clean`` is ``False`` because diagnostic-mode runs
    require a pinned commit).
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover — no git
        return False, "git not available on PATH"
    if result.returncode != 0:
        return False, (result.stderr or "git status failed").strip()
    summary = result.stdout.strip()
    return (summary == ""), summary


def capture_environment() -> Environment:
    """Snapshot the current execution environment."""
    return Environment(
        openpathai_version=_read_openpathai_version(),
        python_version=sys.version.split()[0],
        platform=_platform.platform(),
        machine=_platform.machine(),
        git_commit=_git_commit(),
    )


class Environment(BaseModel):
    model_config = ConfigDict(frozen=True)

    openpathai_version: str
    python_version: str
    platform: str
    machine: str
    git_commit: str | None = None


class CacheStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses


class NodeRunRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str
    op: str
    cache_key: str
    cache_hit: bool
    code_hash: str
    started_at: datetime
    ended_at: datetime
    input_config: dict[str, Any] = Field(default_factory=dict)
    input_hashes: dict[str, str] = Field(default_factory=dict)
    output_artifact_type: str
    output_hash: str


class RunManifest(BaseModel):
    """A complete audit record for one pipeline execution."""

    model_config = ConfigDict(frozen=True)

    manifest_version: str = MANIFEST_VERSION
    run_id: str
    pipeline_id: str
    pipeline_graph_hash: str
    mode: Mode = "exploratory"
    timestamp_start: datetime
    timestamp_end: datetime
    environment: Environment
    steps: list[NodeRunRecord] = Field(default_factory=list)
    cache_stats: CacheStats = Field(default_factory=CacheStats)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @property
    def status(self) -> Literal["success"]:
        """Phase 1 only produces successful manifests; failures raise."""
        return "success"

    @classmethod
    def compute_graph_hash(cls, pipeline_spec: dict[str, Any]) -> str:
        """Canonical SHA-256 of a pipeline spec (shape-only, not per-run)."""
        return canonical_sha256(pipeline_spec)

    def to_json(self, *, indent: int | None = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> RunManifest:
        return cls.model_validate_json(raw)


# Pydantic needs to see the order here — Environment must be declared
# before RunManifest (it is), and NodeRunRecord before RunManifest (it
# is). Rebuild for forward-ref safety when imported from __future__.
RunManifest.model_rebuild()
