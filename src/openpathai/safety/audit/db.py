"""SQLite-backed :class:`AuditDB` and typed row structs.

Every analyse / training / pipeline run lands here. The DB file is
opened in WAL mode so the GUI's Runs tab can poll while a training
run writes. Every insert/update/delete is wrapped in a short-lived
connection (we do not cache a long-lived handle) to keep
multi-threaded GUI usage safe.

Schema is defined in :mod:`openpathai.safety.audit.schema`; the SQL
lives there so it is unit-testable without opening a real DB.

Row structs are frozen pydantic models — the CLI prints them, the
GUI renders them, the diff module reads their attributes.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from openpathai.safety.audit.phi import redact_manifest_path, strip_phi
from openpathai.safety.audit.schema import ALL_DDL, SCHEMA_VERSION

__all__ = [
    "AnalysisEntry",
    "AuditDB",
    "AuditEntry",
    "PipelineEntry",
    "RunKind",
    "RunMode",
    "RunStatus",
    "TrainingEntry",
]


RunKind = Literal["pipeline", "training"]
RunMode = Literal["exploratory", "diagnostic"]
RunStatus = Literal["running", "success", "failed", "aborted"]
AnalysisDecision = Literal["positive", "negative", "review"]
AnalysisBand = Literal["low", "between", "high"]


def _utcnow_iso() -> str:
    """Return an ISO-8601 UTC timestamp (no microseconds for readability)."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------- #
# Row models
# --------------------------------------------------------------------------- #


class AuditEntry(BaseModel):
    """One ``runs`` row — applies to pipeline + training runs alike.

    Diff-able (``diff_runs`` reads attributes from this struct).

    ``extra="ignore"`` is deliberate: the DB is read via
    ``AuditEntry(**dict(sqlite3.Row))`` over ``SELECT *`` so a future
    migration that adds a column must not brick existing reader code.
    ``frozen=True`` still guarantees immutability.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    run_id: str = Field(min_length=1)
    kind: RunKind
    mode: RunMode = "exploratory"
    timestamp_start: str
    timestamp_end: str | None = None
    pipeline_yaml_hash: str = ""
    graph_hash: str = ""
    git_commit: str = ""
    tier: str = "unknown"
    status: RunStatus = "running"
    metrics_json: str | None = None
    manifest_path: str = ""


class TrainingEntry(AuditEntry):
    """Marker subclass — ``kind`` must be ``"training"``."""

    kind: Literal["training"] = "training"


class PipelineEntry(AuditEntry):
    """Marker subclass — ``kind`` must be ``"pipeline"``."""

    kind: Literal["pipeline"] = "pipeline"


class AnalysisEntry(BaseModel):
    """One ``analyses`` row — from a Phase 7 :class:`AnalysisResult`.

    ``filename_hash`` is the SHA-256 of the input file basename; the
    original path is **never** persisted (master-plan §17 PHI rule).

    ``extra="ignore"`` — see :class:`AuditEntry` docstring for rationale.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    analysis_id: str = Field(min_length=1)
    run_id: str | None = None
    filename_hash: str
    image_sha256: str
    timestamp: str
    prediction: str
    confidence: float = Field(ge=0.0, le=1.0)
    decision: AnalysisDecision
    band: AnalysisBand
    mode: RunMode = "exploratory"
    model_id: str
    pipeline_yaml_hash: str = ""


# --------------------------------------------------------------------------- #
# DB class
# --------------------------------------------------------------------------- #


class AuditDB:
    """SQLite wrapper over ``~/.openpathai/audit.db``.

    Use :meth:`open_default` to get the process-default location (honours
    ``OPENPATHAI_HOME``) or :meth:`open_path` to point at an arbitrary
    file (tests prefer the latter).
    """

    def __init__(self, path: str | Path):
        self._path = Path(path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._bootstrap()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def open_default(cls) -> AuditDB:
        """Open the process-default DB (``$OPENPATHAI_HOME/audit.db``)."""
        from openpathai.safety.audit import default_audit_db_path

        return cls(default_audit_db_path())

    @classmethod
    def open_path(cls, path: str | Path) -> AuditDB:
        """Open a DB at ``path``. Used by tests + custom deployments."""
        return cls(path)

    @property
    def path(self) -> Path:
        return self._path

    def _bootstrap(self) -> None:
        """Create tables + record the schema version if needed."""
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("PRAGMA foreign_keys=ON;")
            for stmt in ALL_DDL:
                conn.execute(stmt)
            row = conn.execute(
                "SELECT version FROM schema_info ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_info (version, applied_at_utc) VALUES (?, ?)",
                    (SCHEMA_VERSION, _utcnow_iso()),
                )
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Short-lived connection — one per call. Thread-safe by default."""
        conn = sqlite3.connect(self._path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:  # pragma: no cover - kept for symmetry with other wrappers
        """No-op — we never hold a long-lived connection."""

    # ------------------------------------------------------------------
    # Inserts
    # ------------------------------------------------------------------

    def insert_run(
        self,
        *,
        kind: RunKind,
        mode: RunMode = "exploratory",
        pipeline_yaml_hash: str = "",
        graph_hash: str = "",
        git_commit: str = "",
        tier: str = "unknown",
        status: RunStatus = "running",
        metrics: dict[str, Any] | None = None,
        manifest_path: str = "",
        run_id: str | None = None,
        timestamp_start: str | None = None,
        timestamp_end: str | None = None,
    ) -> AuditEntry:
        """Insert a new ``runs`` row; return the stored :class:`AuditEntry`.

        Automatically strips PHI from the ``metrics`` dict before it
        lands in ``metrics_json``.
        """
        run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        timestamp_start = timestamp_start or _utcnow_iso()
        metrics_blob = (
            json.dumps(strip_phi(metrics), sort_keys=True) if metrics is not None else None
        )
        # PHI guard (iron rule #8): never persist raw filesystem paths
        # in ``runs.manifest_path``. Parent directories can encode
        # patient context (``/Users/dr-smith/patient_042/…``), so we
        # redact to ``<basename>#<sha256-of-parent[:8]>`` before the
        # column ever touches SQLite.
        safe_manifest_path = redact_manifest_path(manifest_path)
        entry = AuditEntry(
            run_id=run_id,
            kind=kind,
            mode=mode,
            timestamp_start=timestamp_start,
            timestamp_end=timestamp_end,
            pipeline_yaml_hash=pipeline_yaml_hash,
            graph_hash=graph_hash,
            git_commit=git_commit,
            tier=tier,
            status=status,
            metrics_json=metrics_blob,
            manifest_path=safe_manifest_path,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, kind, mode, timestamp_start, timestamp_end,
                    pipeline_yaml_hash, graph_hash, git_commit, tier,
                    status, metrics_json, manifest_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.run_id,
                    entry.kind,
                    entry.mode,
                    entry.timestamp_start,
                    entry.timestamp_end,
                    entry.pipeline_yaml_hash,
                    entry.graph_hash,
                    entry.git_commit,
                    entry.tier,
                    entry.status,
                    entry.metrics_json,
                    entry.manifest_path,
                ),
            )
        return entry

    def update_run_status(
        self,
        run_id: str,
        *,
        status: RunStatus,
        timestamp_end: str | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Finalise a run — set status + optional end-time and metrics."""
        with self._connect() as conn:
            params: list[Any] = [status]
            pieces: list[str] = ["status = ?"]
            if timestamp_end is not None:
                pieces.append("timestamp_end = ?")
                params.append(timestamp_end)
            if metrics is not None:
                pieces.append("metrics_json = ?")
                params.append(json.dumps(strip_phi(metrics), sort_keys=True))
            params.append(run_id)
            conn.execute(
                f"UPDATE runs SET {', '.join(pieces)} WHERE run_id = ?",
                tuple(params),
            )

    def insert_analysis(
        self,
        *,
        filename_hash: str,
        image_sha256: str,
        prediction: str,
        confidence: float,
        decision: AnalysisDecision,
        band: AnalysisBand,
        mode: RunMode = "exploratory",
        model_id: str = "",
        pipeline_yaml_hash: str = "",
        run_id: str | None = None,
        analysis_id: str | None = None,
        timestamp: str | None = None,
    ) -> AnalysisEntry:
        """Insert a new ``analyses`` row; return the stored entry."""
        analysis_id = analysis_id or f"anz-{uuid.uuid4().hex[:12]}"
        timestamp = timestamp or _utcnow_iso()
        entry = AnalysisEntry(
            analysis_id=analysis_id,
            run_id=run_id,
            filename_hash=filename_hash,
            image_sha256=image_sha256,
            timestamp=timestamp,
            prediction=prediction,
            confidence=float(confidence),
            decision=decision,
            band=band,
            mode=mode,
            model_id=model_id,
            pipeline_yaml_hash=pipeline_yaml_hash,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analyses (
                    analysis_id, run_id, filename_hash, image_sha256, timestamp,
                    prediction, confidence, decision, band, mode,
                    model_id, pipeline_yaml_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.analysis_id,
                    entry.run_id,
                    entry.filename_hash,
                    entry.image_sha256,
                    entry.timestamp,
                    entry.prediction,
                    entry.confidence,
                    entry.decision,
                    entry.band,
                    entry.mode,
                    entry.model_id,
                    entry.pipeline_yaml_hash,
                ),
            )
        return entry

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_runs(
        self,
        *,
        kind: RunKind | None = None,
        since: str | None = None,
        until: str | None = None,
        status: RunStatus | None = None,
        limit: int = 100,
    ) -> tuple[AuditEntry, ...]:
        clauses: list[str] = []
        params: list[Any] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if since is not None:
            clauses.append("timestamp_start >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp_start <= ?")
            params.append(until)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        sql = f"""
            SELECT * FROM runs
            {where}
            ORDER BY timestamp_start DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return tuple(AuditEntry(**dict(row)) for row in rows)

    def get_run(self, run_id: str) -> AuditEntry | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return AuditEntry(**dict(row)) if row else None

    def list_analyses(
        self,
        *,
        run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[AnalysisEntry, ...]:
        clauses: list[str] = []
        params: list[Any] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        sql = f"""
            SELECT * FROM analyses
            {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return tuple(AnalysisEntry(**dict(row)) for row in rows)

    def get_analysis(self, analysis_id: str) -> AnalysisEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,)
            ).fetchone()
        return AnalysisEntry(**dict(row)) if row else None

    # ------------------------------------------------------------------
    # Deletes
    # ------------------------------------------------------------------

    def delete_before(self, cutoff_utc: str) -> dict[str, int]:
        """Delete rows with ``timestamp_start`` (runs) or ``timestamp``
        (analyses) strictly earlier than ``cutoff_utc``.

        Returns a dict ``{"runs": N, "analyses": M}`` of deleted counts.
        Authorisation is the caller's responsibility — see
        :class:`openpathai.safety.audit.token.KeyringTokenStore`.
        """
        with self._connect() as conn:
            runs_cur = conn.execute("DELETE FROM runs WHERE timestamp_start < ?", (cutoff_utc,))
            runs_deleted = runs_cur.rowcount
            anz_cur = conn.execute("DELETE FROM analyses WHERE timestamp < ?", (cutoff_utc,))
            anz_deleted = anz_cur.rowcount
        return {"runs": int(runs_deleted), "analyses": int(anz_deleted)}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Count rows + report DB size + schema version."""
        with self._connect() as conn:
            runs_total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            per_kind = {
                row[0]: row[1]
                for row in conn.execute("SELECT kind, COUNT(*) FROM runs GROUP BY kind").fetchall()
            }
            analyses_total = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
            schema_row = conn.execute(
                "SELECT version FROM schema_info ORDER BY version DESC LIMIT 1"
            ).fetchone()
        size_bytes = self._path.stat().st_size if self._path.exists() else 0
        return {
            "path": str(self._path),
            "size_bytes": int(size_bytes),
            "schema_version": int(schema_row[0]) if schema_row else SCHEMA_VERSION,
            "runs": int(runs_total),
            "runs_per_kind": {k: int(v) for k, v in per_kind.items()},
            "analyses": int(analyses_total),
        }
