"""In-process async job runner (Phase 19).

Simple, mature plumbing: a ``ThreadPoolExecutor`` runs submitted
callables, and this class keeps a dict of ``run_id -> JobRecord``
so the FastAPI routes can poll status + retrieve results.

Scope:
- Phase 19 ships single-machine, small-concurrency (default 1).
- Phase 22+ may swap in a distributed runner.

Cancellation semantics: once a job has started we can only request
cancellation cooperatively. The Phase-1 executor does not ship a
checkpoint loop, so cancellation of a running job is effectively
"wait for it to finish then mark as cancelled" in this iteration.
Queued jobs cancel instantly.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

__all__ = [
    "JobRecord",
    "JobRunner",
    "JobStatus",
]


JobStatus = Literal["queued", "running", "success", "error", "cancelled"]


@dataclass
class JobRecord:
    """Runtime state of one submitted job."""

    run_id: str
    status: JobStatus
    submitted_at: str
    started_at: str | None = None
    ended_at: str | None = None
    error: str | None = None
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_public(self) -> dict[str, Any]:
        """Wire-safe representation — excludes the raw ``result``
        (which may be a pydantic manifest or similar)."""
        return {
            "run_id": self.run_id,
            "status": self.status,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


def _utcnow() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class JobRunner:
    """Thread-pool-backed runner for pipeline executions.

    Designed to be reused across requests — construct once, hand
    to the FastAPI app at startup. Safe for concurrent ``submit``
    and ``get`` calls.
    """

    def __init__(self, *, max_workers: int = 1) -> None:
        if max_workers < 1:
            raise ValueError(f"max_workers must be >= 1; got {max_workers}")
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="openpathai-runs",
        )
        self._records: dict[str, JobRecord] = {}
        self._futures: dict[str, Future[Any]] = {}
        self._lock = threading.RLock()

    # ─── Submission ───────────────────────────────────────────────

    def submit(
        self,
        fn: Callable[[], Any],
        *,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JobRecord:
        """Queue ``fn`` for execution. Returns the initial
        :class:`JobRecord` (status = ``"queued"``)."""
        rid = run_id or uuid.uuid4().hex
        with self._lock:
            if rid in self._records:
                raise ValueError(f"duplicate run_id {rid!r}")
            record = JobRecord(
                run_id=rid,
                status="queued",
                submitted_at=_utcnow(),
                metadata=dict(metadata or {}),
            )
            self._records[rid] = record
            future = self._pool.submit(self._wrap, rid, fn)
            self._futures[rid] = future
        return record

    def _wrap(self, run_id: str, fn: Callable[[], Any]) -> Any:
        # Entered on a pool thread.
        with self._lock:
            record = self._records[run_id]
            if record.status == "cancelled":
                # Cancelled while queued — skip.
                return None
            record.status = "running"
            record.started_at = _utcnow()
        try:
            result = fn()
            with self._lock:
                rec = self._records[run_id]
                if rec.status != "cancelled":
                    rec.status = "success"
                    rec.result = result
                    rec.ended_at = _utcnow()
            return result
        except Exception as exc:
            with self._lock:
                rec = self._records[run_id]
                if rec.status != "cancelled":
                    rec.status = "error"
                    rec.error = f"{type(exc).__name__}: {exc!s}"
                    rec.ended_at = _utcnow()
                    rec.metadata["traceback"] = traceback.format_exc()
            raise

    # ─── Queries ──────────────────────────────────────────────────

    def get(self, run_id: str) -> JobRecord | None:
        with self._lock:
            return self._records.get(run_id)

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: JobStatus | None = None,
    ) -> tuple[list[JobRecord], int]:
        """Return a page of records + the total count (post-filter)."""
        with self._lock:
            rows = sorted(
                self._records.values(),
                key=lambda r: r.submitted_at,
                reverse=True,
            )
        if status is not None:
            rows = [r for r in rows if r.status == status]
        total = len(rows)
        return rows[offset : offset + limit], total

    # ─── Mutation ─────────────────────────────────────────────────

    def cancel(self, run_id: str) -> bool:
        """Mark the job as cancelled. Returns ``True`` if the job
        was queued (and therefore cancellable immediately) or already
        finished; ``False`` if the job was actively running — the
        caller should poll for completion."""
        with self._lock:
            record = self._records.get(run_id)
            future = self._futures.get(run_id)
        if record is None:
            return False
        if record.status in {"success", "error", "cancelled"}:
            return True
        if future is not None and future.cancel():
            with self._lock:
                record.status = "cancelled"
                record.ended_at = _utcnow()
            return True
        # Running; best-effort mark so the wrap-up sees it.
        with self._lock:
            if record.status == "running":
                record.status = "cancelled"
                record.ended_at = _utcnow()
        return False

    def shutdown(self, wait: bool = True) -> None:
        """Tear down the thread pool (idempotent)."""
        self._pool.shutdown(wait=wait, cancel_futures=not wait)

    # ─── Context manager convenience ──────────────────────────────

    def __enter__(self) -> JobRunner:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown(wait=False)
