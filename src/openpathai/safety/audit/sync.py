"""Import a Colab-produced (or otherwise remote) :class:`RunManifest`
into the local audit DB.

Phase 11's half of the reproducibility round-trip: the user runs a
pipeline on Colab, downloads ``manifest.json``, and calls
``openpathai sync <manifest.json>``. The importer:

* Parses the file via :meth:`RunManifest.from_json` (pydantic).
* Inserts a ``runs`` row that preserves the manifest's original
  ``run_id`` — so the Phase 8 Runs tab, ``openpathai diff``, and
  ``openpathai audit show`` all work on the Colab-produced row.
* Is **idempotent** — re-importing the same manifest logs a warning
  and returns the existing row instead of duplicating.

The import is tolerant: unknown manifest keys (added by newer
versions of OpenPathAI) are dropped rather than failing the import,
consistent with the Phase-10 "audit DB is manifest-schema-agnostic"
invariant.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openpathai.safety.audit.db import AuditDB, AuditEntry

__all__ = [
    "ManifestImportError",
    "import_manifest",
    "preview_manifest",
]


_LOGGER = logging.getLogger(__name__)


class ManifestImportError(ValueError):
    """Raised when a manifest file cannot be parsed or imported."""


def _load_manifest_payload(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser()
    if not target.is_file():
        raise ManifestImportError(f"Manifest file not found: {target}")
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestImportError(f"Could not read {target}: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestImportError(f"{target} is not a valid JSON RunManifest: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ManifestImportError(f"{target} must be a JSON mapping; got {type(payload).__name__}")
    return payload


def _require_fields(payload: dict[str, Any], *, source: str) -> None:
    required = {"run_id", "pipeline_id", "pipeline_graph_hash", "timestamp_start"}
    missing = required - set(payload)
    if missing:
        raise ManifestImportError(
            f"{source} is missing required RunManifest fields: {sorted(missing)}"
        )


def preview_manifest(path: str | Path) -> dict[str, Any]:
    """Return the audit-row shape that :func:`import_manifest` would write.

    No DB writes, no audit hooks. Useful for the CLI's ``--show`` flag
    so users can inspect what will land before committing.
    """
    payload = _load_manifest_payload(path)
    _require_fields(payload, source=str(path))

    metrics_obj = payload.get("cache_stats")
    if isinstance(metrics_obj, dict):
        metrics = {
            "hits": int(metrics_obj.get("hits", 0)),
            "misses": int(metrics_obj.get("misses", 0)),
        }
    else:
        metrics = {}

    return {
        "run_id": payload["run_id"],
        "kind": "pipeline",
        "mode": payload.get("mode", "exploratory"),
        "timestamp_start": payload["timestamp_start"],
        "timestamp_end": payload.get("timestamp_end"),
        "pipeline_yaml_hash": payload.get("pipeline_graph_hash", ""),
        "graph_hash": payload.get("pipeline_graph_hash", ""),
        "git_commit": _git_commit_from_env(payload),
        "tier": _tier_from_env(payload),
        "status": "success",
        "metrics": metrics,
        "manifest_path": str(Path(path).expanduser().resolve()),
    }


def _git_commit_from_env(payload: dict[str, Any]) -> str:
    env = payload.get("environment")
    if isinstance(env, dict):
        return str(env.get("git_commit", ""))
    return ""


def _tier_from_env(payload: dict[str, Any]) -> str:
    env = payload.get("environment")
    if isinstance(env, dict):
        return str(env.get("tier", "unknown"))
    return "unknown"


def import_manifest(
    path: str | Path,
    *,
    db: AuditDB | None = None,
) -> AuditEntry:
    """Import the manifest at ``path`` into the audit DB.

    Returns the inserted (or existing, on idempotent re-import)
    :class:`AuditEntry`. Raises :class:`ManifestImportError` on a
    parse / validation failure.
    """
    preview = preview_manifest(path)
    target_db = db if db is not None else AuditDB.open_default()

    existing = target_db.get_run(preview["run_id"])
    if existing is not None:
        _LOGGER.warning(
            "Manifest %s already imported as run %s — leaving existing row untouched.",
            path,
            preview["run_id"],
        )
        return existing

    return target_db.insert_run(
        kind="pipeline",
        mode=preview["mode"],
        pipeline_yaml_hash=preview["pipeline_yaml_hash"],
        graph_hash=preview["graph_hash"],
        git_commit=preview["git_commit"],
        tier=preview["tier"],
        status=preview["status"],
        metrics=preview["metrics"],
        manifest_path=preview["manifest_path"],
        run_id=preview["run_id"],
        timestamp_start=preview["timestamp_start"],
        timestamp_end=preview["timestamp_end"],
    )
