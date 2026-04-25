"""Read-only passthrough to the Phase-8 audit DB (Phase 19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from openpathai.server.auth import AuthDependency

__all__ = ["router"]


router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[AuthDependency],
)


def _open_db(request: Request):
    from openpathai.safety.audit import AuditDB

    root = request.app.state.settings.openpathai_home
    db_path = root / "audit.db"
    if db_path.is_file():
        return AuditDB(db_path)
    return AuditDB.open_default()


@router.get("/runs", summary="Audit-DB recent runs")
async def list_audit_runs(
    request: Request,
    kind: str | None = Query(default=None),
    run_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    allowed_kind = {"training", "analysis", "export", None}
    allowed_status = {"success", "fail", "cancelled", None}
    if kind not in allowed_kind:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"kind must be one of {sorted(k for k in allowed_kind if k)}",
        )
    if run_status not in allowed_status:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of {sorted(s for s in allowed_status if s)}",
        )
    db = _open_db(request)
    rows = db.list_runs(
        kind=kind,  # type: ignore[arg-type]
        status=run_status,  # type: ignore[arg-type]
        limit=limit,
    )
    return {
        "items": [r.model_dump(mode="json") for r in rows],
        "total": len(rows),
        "limit": limit,
    }


@router.get("/runs/{run_id}", summary="Audit-DB entry for one run")
async def get_audit_run(request: Request, run_id: str) -> dict[str, Any]:
    db = _open_db(request)
    entry = db.get_run(run_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"audit row for run {run_id!r} not found",
        )
    return entry.model_dump(mode="json")


@router.get(
    "/runs/{run_id}/full",
    summary="Audit row + Phase-17 manifest + signature info (Phase 21)",
)
async def get_audit_run_full(request: Request, run_id: str) -> dict[str, Any]:
    """Resolve a ``run_id`` to (a) its audit-DB row + (b) the in-memory
    Phase-17 manifest if the run is still tracked by the JobRunner +
    (c) sigstore signature metadata when Diagnostic mode signed it.

    Returns 404 only when neither source has the run."""
    runner = getattr(request.app.state, "job_runner", None)
    job = runner.get(run_id) if runner is not None else None
    db = _open_db(request)
    audit_row = db.get_run(run_id)
    analyses = db.list_analyses(run_id=run_id, limit=200)

    manifest: dict[str, Any] | None = None
    cache_stats: dict[str, Any] | None = None
    if job is not None and isinstance(job.result, dict):
        manifest = job.result.get("manifest")
        cache_stats = job.result.get("cache_stats")

    if audit_row is None and job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no audit or runtime record for run {run_id!r}",
        )

    signature: dict[str, Any] | None = None
    if manifest and isinstance(manifest, dict):
        sig = manifest.get("signature") or manifest.get("sigstore")
        if isinstance(sig, dict):
            signature = sig

    return {
        "run_id": run_id,
        "audit": audit_row.model_dump(mode="json") if audit_row is not None else None,
        "runtime": job.to_public() if job is not None else None,
        "manifest": manifest,
        "cache_stats": cache_stats,
        "analyses": [a.model_dump(mode="json") for a in analyses],
        "signature": signature,
    }


@router.get("/analyses", summary="Audit-DB analyses (optionally filtered by run)")
async def list_audit_analyses(
    request: Request,
    run_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    db = _open_db(request)
    rows = db.list_analyses(run_id=run_id, limit=limit)
    return {
        "items": [r.model_dump(mode="json") for r in rows],
        "total": len(rows),
        "limit": limit,
    }
