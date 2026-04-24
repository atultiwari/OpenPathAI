"""Fire-and-forget hooks called after every successful run.

Every hook:

1. No-ops when :func:`openpathai.safety.audit.audit_enabled` is ``False``.
2. Swallows any exception, logs a warning, and returns an empty
   string — the iron rule here is *audit failure must not break a
   real run*.
3. Strips PHI from any caller-supplied params dict before writing.

Callers supply as much context as they have; missing fields default
to empty strings so a minimal smoke run still produces a row.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from openpathai.safety.audit.db import (
    AnalysisEntry,
    AuditDB,
    AuditEntry,
    RunMode,
)
from openpathai.safety.audit.phi import hash_filename, strip_phi

if TYPE_CHECKING:  # pragma: no cover - type-only
    from openpathai.safety.result import AnalysisResult

__all__ = [
    "log_analysis",
    "log_pipeline",
    "log_training",
]


_LOGGER = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _enabled() -> bool:
    """Late import to avoid a cycle with the package ``__init__``."""
    from openpathai.safety.audit import audit_enabled

    return audit_enabled()


def _db(db: AuditDB | None) -> AuditDB:
    if db is not None:
        return db
    return AuditDB.open_default()


# --------------------------------------------------------------------------- #
# log_analysis
# --------------------------------------------------------------------------- #


def log_analysis(
    result: AnalysisResult,
    *,
    input_path: str | Path | None = None,
    run_id: str | None = None,
    mode: RunMode = "exploratory",
    pipeline_yaml_hash: str = "",
    db: AuditDB | None = None,
) -> str:
    """Persist one :class:`AnalysisResult` as an ``analyses`` row.

    Returns the new ``analysis_id`` (empty string on failure).
    """
    if not _enabled():
        return ""
    try:
        target = _db(db)
        filename_hash = hash_filename(input_path) if input_path is not None else ""
        entry: AnalysisEntry = target.insert_analysis(
            filename_hash=filename_hash,
            image_sha256=result.image_sha256,
            prediction=result.predicted_class_name,
            confidence=float(result.borderline.confidence),
            decision=result.borderline.decision,
            band=result.borderline.band,
            mode=mode,
            model_id=result.model_name,
            pipeline_yaml_hash=pipeline_yaml_hash,
            run_id=run_id,
            timestamp=result.timestamp.astimezone(UTC).replace(microsecond=0).isoformat()
            if result.timestamp.tzinfo is not None
            else _utcnow_iso(),
        )
        return entry.analysis_id
    except Exception as exc:
        _LOGGER.warning("log_analysis failed (non-fatal): %s", exc)
        return ""


# --------------------------------------------------------------------------- #
# log_training
# --------------------------------------------------------------------------- #


def log_training(
    *,
    model_id: str,
    dataset_id: str = "",
    git_commit: str = "",
    pipeline_yaml_hash: str = "",
    graph_hash: str = "",
    tier: str = "unknown",
    mode: RunMode = "exploratory",
    manifest_path: str = "",
    metrics: dict[str, Any] | None = None,
    status: Literal["success", "failed", "aborted"] = "success",
    run_id: str | None = None,
    db: AuditDB | None = None,
) -> str:
    """Persist a completed training run.

    ``metrics`` is run through :func:`strip_phi` before it lands in
    ``metrics_json``. Returns the new ``run_id`` (empty on failure).
    """
    if not _enabled():
        return ""
    try:
        target = _db(db)
        merged: dict[str, Any] = {"model_id": model_id, "dataset_id": dataset_id}
        if metrics:
            merged.update(metrics)
        entry: AuditEntry = target.insert_run(
            kind="training",
            mode=mode,
            pipeline_yaml_hash=pipeline_yaml_hash,
            graph_hash=graph_hash,
            git_commit=git_commit,
            tier=tier,
            status=status,
            metrics=strip_phi(merged),
            manifest_path=manifest_path,
            run_id=run_id,
            timestamp_end=_utcnow_iso(),
        )
        return entry.run_id
    except Exception as exc:
        _LOGGER.warning("log_training failed (non-fatal): %s", exc)
        return ""


# --------------------------------------------------------------------------- #
# log_pipeline
# --------------------------------------------------------------------------- #


def log_pipeline(
    manifest: Any,
    *,
    mode: RunMode = "exploratory",
    tier: str = "unknown",
    git_commit: str = "",
    manifest_path: str = "",
    status: Literal["success", "failed", "aborted"] = "success",
    db: AuditDB | None = None,
) -> str:
    """Persist a completed pipeline run from a Phase 1 :class:`RunManifest`.

    Pulls the pipeline hash / graph hash / metrics out of ``manifest``
    via public attributes — duck-typed so the caller may also pass a
    plain mapping. Returns the new ``run_id`` (empty on failure).
    """
    if not _enabled():
        return ""
    try:
        target = _db(db)
        pipeline_yaml_hash = str(getattr(manifest, "pipeline_hash", ""))
        graph_hash = str(getattr(manifest, "graph_hash", ""))
        metrics_obj = getattr(manifest, "metrics", None)
        if metrics_obj is None and isinstance(manifest, dict):
            pipeline_yaml_hash = pipeline_yaml_hash or str(manifest.get("pipeline_hash", ""))
            graph_hash = graph_hash or str(manifest.get("graph_hash", ""))
            metrics_obj = manifest.get("metrics")
        metrics_dict: dict[str, Any]
        if metrics_obj is None:
            metrics_dict = {}
        elif isinstance(metrics_obj, str):
            try:
                loaded = json.loads(metrics_obj)
                metrics_dict = loaded if isinstance(loaded, dict) else {"raw": loaded}
            except json.JSONDecodeError:
                metrics_dict = {"raw": metrics_obj}
        elif isinstance(metrics_obj, dict):
            metrics_dict = metrics_obj
        else:
            metrics_dict = {"value": str(metrics_obj)}

        entry: AuditEntry = target.insert_run(
            kind="pipeline",
            mode=mode,
            pipeline_yaml_hash=pipeline_yaml_hash,
            graph_hash=graph_hash,
            git_commit=git_commit,
            tier=tier,
            status=status,
            metrics=strip_phi(metrics_dict),
            manifest_path=manifest_path,
            timestamp_end=_utcnow_iso(),
        )
        return entry.run_id
    except Exception as exc:
        _LOGGER.warning("log_pipeline failed (non-fatal): %s", exc)
        return ""
