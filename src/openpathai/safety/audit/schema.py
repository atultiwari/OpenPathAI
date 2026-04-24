"""Audit DB schema — master-plan §16.3 + Phase 8 additions.

Three small extensions beyond the master-plan SQL block (all listed in
``phase-08-audit-history-diff.md`` §3.1 so the delta is recorded):

* ``runs.kind`` — distinguishes pipeline runs from training runs.
* ``runs.timestamp_end`` — enables duration display in the GUI.
* ``analyses.{image_sha256, decision, band}`` — the Phase 7 borderline
  outputs make an analysis row useful without joining back to a PDF.

A ``schema_info`` table holds ``(version INTEGER, applied_at_utc
TEXT)`` so a future phase can add migrations without churning the file
layout. We ship only version ``1`` in Phase 8.
"""

from __future__ import annotations

__all__ = [
    "ALL_DDL",
    "ANALYSES_DDL",
    "RUNS_DDL",
    "SCHEMA_INFO_DDL",
    "SCHEMA_VERSION",
    "TABLE_NAMES",
]


SCHEMA_VERSION: int = 1
"""Bumped whenever the DDL changes in a non-backward-compatible way."""


TABLE_NAMES: tuple[str, ...] = ("schema_info", "runs", "analyses")


SCHEMA_INFO_DDL: str = """
CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL
);
""".strip()


RUNS_DDL: str = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('pipeline', 'training')),
    mode TEXT NOT NULL CHECK(mode IN ('exploratory', 'diagnostic')),
    timestamp_start TEXT NOT NULL,
    timestamp_end TEXT,
    pipeline_yaml_hash TEXT NOT NULL,
    graph_hash TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    tier TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running', 'success', 'failed', 'aborted')),
    metrics_json TEXT,
    manifest_path TEXT NOT NULL
);
""".strip()


RUNS_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_runs_kind_start ON runs(kind, timestamp_start DESC);",
    "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);",
)


ANALYSES_DDL: str = """
CREATE TABLE IF NOT EXISTS analyses (
    analysis_id TEXT PRIMARY KEY,
    run_id TEXT,
    filename_hash TEXT NOT NULL,
    image_sha256 TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    prediction TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
    decision TEXT NOT NULL CHECK(decision IN ('positive', 'negative', 'review')),
    band TEXT NOT NULL CHECK(band IN ('low', 'between', 'high')),
    mode TEXT NOT NULL CHECK(mode IN ('exploratory', 'diagnostic')),
    model_id TEXT NOT NULL,
    pipeline_yaml_hash TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE SET NULL
);
""".strip()


ANALYSES_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_analyses_timestamp ON analyses(timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_analyses_run_id ON analyses(run_id);",
)


ALL_DDL: tuple[str, ...] = (
    SCHEMA_INFO_DDL,
    RUNS_DDL,
    *RUNS_INDEXES,
    ANALYSES_DDL,
    *ANALYSES_INDEXES,
)
"""Every DDL statement in the canonical apply order. Idempotent —
``IF NOT EXISTS`` on every statement so re-opening an existing DB is a
no-op."""
