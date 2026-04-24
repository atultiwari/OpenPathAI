"""Audit trail layer — SQLite-backed run log (Phase 8).

Complements Phase 7's per-run safety surface (borderline / PDF /
model-card contract) with the **history** surface: every analysis,
training, and pipeline run lands in ``~/.openpathai/audit.db``,
filenames are SHA-256-hashed before write (master-plan §17 "PHI
handling"), and runs are queryable via an :class:`AuditDB` that the
CLI, GUI, and library all share.

Top-level surface:

* :class:`AuditDB` — the SQLite wrapper.
* :class:`AuditEntry`, :class:`AnalysisEntry`, :class:`TrainingEntry`,
  :class:`PipelineEntry` — frozen pydantic rows.
* :class:`RunDiff`, :func:`diff_runs` — structured diff of two runs.
* :func:`log_analysis`, :func:`log_training`, :func:`log_pipeline` —
  fire-and-forget hooks the CLI / GUI call after every successful run.
* :func:`audit_enabled`, :func:`default_audit_db_path` — helpers.
* :func:`hash_filename`, :func:`strip_phi` — PHI guards.
* :class:`KeyringTokenStore` — delete-token backend.

Every hook is a **no-op** when ``OPENPATHAI_AUDIT_ENABLED=0``, and
each hook runs inside ``try / except Exception`` so an audit failure
(e.g. full disk, corrupt DB) **must not** surface as a training /
inference failure.
"""

from __future__ import annotations

import os
from pathlib import Path

from openpathai.safety.audit.db import (
    AnalysisEntry,
    AuditDB,
    AuditEntry,
    PipelineEntry,
    TrainingEntry,
)
from openpathai.safety.audit.diff import RunDiff, diff_runs
from openpathai.safety.audit.hooks import (
    log_analysis,
    log_pipeline,
    log_training,
)
from openpathai.safety.audit.phi import hash_filename, strip_phi
from openpathai.safety.audit.schema import SCHEMA_VERSION
from openpathai.safety.audit.sync import (
    ManifestImportError,
    import_manifest,
    preview_manifest,
)
from openpathai.safety.audit.token import KeyringTokenStore

__all__ = [
    "SCHEMA_VERSION",
    "AnalysisEntry",
    "AuditDB",
    "AuditEntry",
    "KeyringTokenStore",
    "ManifestImportError",
    "PipelineEntry",
    "RunDiff",
    "TrainingEntry",
    "audit_enabled",
    "default_audit_db_path",
    "diff_runs",
    "hash_filename",
    "import_manifest",
    "log_analysis",
    "log_pipeline",
    "log_training",
    "preview_manifest",
    "strip_phi",
]


def audit_enabled() -> bool:
    """Whether the audit log should be written.

    Reads ``OPENPATHAI_AUDIT_ENABLED`` (default ``"1"`` — on). Any of
    ``{"0", "false", "no", "off"}`` (case-insensitive) disables logging.
    """
    value = os.environ.get("OPENPATHAI_AUDIT_ENABLED", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def default_audit_db_path() -> Path:
    """Return the default audit DB location (honours ``OPENPATHAI_HOME``)."""
    root = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))
    return root / "audit.db"
