"""Content-addressable cache — filesystem backend.

Cache key formula (see ``docs/planning/master-plan.md`` §9.2)::

    sha256(
        node_id + "::" +
        code_hash + "::" +
        canonical_json(input_config) + "::" +
        canonical_json(sorted(upstream_artifact_hashes))
    )

Storage layout, rooted by default at ``~/.openpathai/cache/``::

    <root>/
    └── <cache_key>/
        ├── artifact.json   # pydantic model_dump_json of the produced Artifact
        └── meta.json       # metadata about this cache entry

Phase 1 scope: a single-process filesystem backend. Remote backends
(Google Drive, S3, R2) slot in as alternative implementations in Phase 10
without changing the public API.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from openpathai.pipeline.schema import Artifact, canonical_json

__all__ = [
    "CacheEntryMeta",
    "ContentAddressableCache",
    "default_cache_root",
]

A = TypeVar("A", bound=Artifact)


def default_cache_root() -> Path:
    """Return the default cache root, ``~/.openpathai/cache/``."""
    return Path.home() / ".openpathai" / "cache"


class CacheEntryMeta(BaseModel):
    """Metadata written alongside each cached artifact."""

    node_id: str
    code_hash: str
    input_config_hash: str
    upstream_hashes: list[str]
    artifact_type: str
    artifact_hash: str
    created_at: float  # Unix timestamp (seconds since epoch)


@dataclass(frozen=True)
class _CachePaths:
    root: Path
    artifact: Path
    meta: Path


class ContentAddressableCache:
    """Filesystem-backed content-addressable cache.

    Parameters
    ----------
    root
        Directory under which cache entries are stored. Defaults to
        ``~/.openpathai/cache/``.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self._root: Path = Path(root) if root is not None else default_cache_root()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    # ─── Key construction ───────────────────────────────────────────────

    @staticmethod
    def key(
        node_id: str,
        code_hash: str,
        input_config: dict | BaseModel,
        upstream_hashes: Iterable[str],
    ) -> str:
        """Compute the content-addressable cache key for a node invocation."""
        if isinstance(input_config, BaseModel):
            config_dict = input_config.model_dump(mode="json")
        else:
            config_dict = input_config
        # Sort upstream hashes so input-ordering doesn't affect the key.
        upstream_sorted = sorted(upstream_hashes)
        payload = "::".join(
            [
                node_id,
                code_hash,
                canonical_json(config_dict),
                canonical_json(upstream_sorted),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ─── Path management ────────────────────────────────────────────────

    def _paths(self, key: str) -> _CachePaths:
        entry_root = self._root / key
        return _CachePaths(
            root=entry_root,
            artifact=entry_root / "artifact.json",
            meta=entry_root / "meta.json",
        )

    # ─── Queries ────────────────────────────────────────────────────────

    def has(self, key: str) -> bool:
        paths = self._paths(key)
        return paths.artifact.exists() and paths.meta.exists()

    def get(self, key: str, artifact_type: type[A]) -> A | None:
        """Load an artifact of the given type, or ``None`` on miss."""
        paths = self._paths(key)
        if not (paths.artifact.exists() and paths.meta.exists()):
            return None
        artifact_raw = paths.artifact.read_text(encoding="utf-8")
        return artifact_type.model_validate_json(artifact_raw)

    def get_meta(self, key: str) -> CacheEntryMeta | None:
        paths = self._paths(key)
        if not paths.meta.exists():
            return None
        return CacheEntryMeta.model_validate_json(paths.meta.read_text(encoding="utf-8"))

    # ─── Writes ─────────────────────────────────────────────────────────

    def put(
        self,
        key: str,
        *,
        node_id: str,
        code_hash: str,
        input_config: dict | BaseModel,
        upstream_hashes: Iterable[str],
        artifact: Artifact,
    ) -> None:
        """Persist an artifact under the given key atomically."""
        paths = self._paths(key)
        paths.root.mkdir(parents=True, exist_ok=True)

        if isinstance(input_config, BaseModel):
            config_dict = input_config.model_dump(mode="json")
        else:
            config_dict = input_config

        meta = CacheEntryMeta(
            node_id=node_id,
            code_hash=code_hash,
            input_config_hash=hashlib.sha256(
                canonical_json(config_dict).encode("utf-8")
            ).hexdigest(),
            upstream_hashes=sorted(upstream_hashes),
            artifact_type=artifact.artifact_type,
            artifact_hash=artifact.content_hash(),
            created_at=time.time(),
        )
        # Write-then-rename for atomicity inside the entry directory.
        artifact_tmp = paths.artifact.with_suffix(".json.tmp")
        meta_tmp = paths.meta.with_suffix(".json.tmp")
        artifact_tmp.write_text(artifact.model_dump_json(), encoding="utf-8")
        meta_tmp.write_text(meta.model_dump_json(), encoding="utf-8")
        artifact_tmp.replace(paths.artifact)
        meta_tmp.replace(paths.meta)

    # ─── Deletion ───────────────────────────────────────────────────────

    def invalidate(self, key: str) -> bool:
        """Remove a cached entry. Returns ``True`` if the entry existed."""
        paths = self._paths(key)
        if not paths.root.exists():
            return False
        shutil.rmtree(paths.root)
        return True

    def clear(self, older_than_days: int | None = None) -> int:
        """Remove cache entries.

        Parameters
        ----------
        older_than_days
            If ``None``, remove every entry. Otherwise, remove only
            entries whose meta's ``created_at`` is older than the
            threshold.

        Returns
        -------
        int
            Number of entries removed.
        """
        removed = 0
        threshold = time.time() - older_than_days * 86400.0 if older_than_days is not None else None
        for entry in self._root.iterdir():
            if not entry.is_dir():
                continue
            if threshold is not None:
                meta_path = entry / "meta.json"
                if not meta_path.exists():
                    continue
                try:
                    meta = CacheEntryMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
                    continue
                if meta.created_at > threshold:
                    continue
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
        return removed
