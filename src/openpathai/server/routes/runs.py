"""Async run execution + status (Phase 19).

``POST /v1/runs`` enqueues a Pipeline for execution on the shared
:class:`openpathai.server.jobs.JobRunner` and returns 202 with the
initial job record. Status polling via ``GET /v1/runs/{run_id}``;
the finished ``RunManifest`` is served from
``GET /v1/runs/{run_id}/manifest`` with PHI already stripped
(the executor's Phase-18-audit ``strip_phi`` fix applies).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from openpathai.pipeline.cache import ContentAddressableCache
from openpathai.pipeline.executor import (
    DiagnosticModeError,
    Executor,
    Pipeline,
)
from openpathai.pipeline.node import REGISTRY as NODE_REGISTRY
from openpathai.server.auth import AuthDependency
from openpathai.server.jobs import JobRecord, JobRunner

__all__ = ["RunRequest", "RunResponse", "router"]


router = APIRouter(
    prefix="/runs",
    tags=["runs"],
    dependencies=[AuthDependency],
)


class RunRequest(BaseModel):
    """Inline run payload: either embed the pipeline or reference a saved one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pipeline: dict[str, Any] | None = None
    saved_pipeline_id: str | None = None
    parallel_mode: Literal["sequential", "thread"] = "sequential"
    max_workers: int | None = Field(default=None, ge=1, le=32)


class RunResponse(BaseModel):
    """Wire shape of ``GET /v1/runs/{id}``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    status: str
    submitted_at: str
    started_at: str | None
    ended_at: str | None
    error: str | None
    metadata: dict[str, Any]


def _get_runner(request: Request) -> JobRunner:
    runner = getattr(request.app.state, "job_runner", None)
    if runner is None:
        runner = JobRunner(max_workers=request.app.state.settings.max_concurrent_runs)
        request.app.state.job_runner = runner
    return runner


def _load_saved_pipeline(request: Request, pipeline_id: str) -> Pipeline:
    import yaml

    root = request.app.state.settings.resolved_pipelines_dir()
    path = root / f"{pipeline_id}.yaml"
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"saved pipeline {pipeline_id!r} not found",
        )
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        return Pipeline.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"saved pipeline is invalid: {exc.errors()}",
        ) from exc


def _pipeline_from_request(request: Request, body: RunRequest) -> Pipeline:
    if body.pipeline and body.saved_pipeline_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pass exactly one of `pipeline` (inline) or `saved_pipeline_id`",
        )
    if body.saved_pipeline_id:
        return _load_saved_pipeline(request, body.saved_pipeline_id)
    if body.pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="either `pipeline` or `saved_pipeline_id` is required",
        )
    try:
        return Pipeline.model_validate(body.pipeline)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc


def _to_record(job: JobRecord) -> RunResponse:
    pub = job.to_public()
    return RunResponse(**pub)


def _make_runner(
    pipeline: Pipeline, *, parallel_mode: str, max_workers: int | None
) -> tuple[Executor, ContentAddressableCache]:
    del pipeline  # reserved for a future per-pipeline cache namespace.
    cache = ContentAddressableCache()
    executor = Executor(
        cache,
        registry=NODE_REGISTRY,
        parallel_mode=parallel_mode,  # type: ignore[arg-type]
        max_workers=max_workers,
    )
    return executor, cache


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a pipeline execution",
    response_model=RunResponse,
)
async def create_run(request: Request, body: RunRequest) -> RunResponse:
    pipeline = _pipeline_from_request(request, body)
    # Reject unknown ops up-front so the 202 is only issued for a
    # dispatchable pipeline.
    unknown = [s.op for s in pipeline.steps if not NODE_REGISTRY.has(s.op)]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown ops: {sorted(set(unknown))}",
        )
    runner = _get_runner(request)

    def _invoke() -> Any:
        executor, _ = _make_runner(
            pipeline,
            parallel_mode=body.parallel_mode,
            max_workers=body.max_workers,
        )
        try:
            result = executor.run(pipeline)
        except DiagnosticModeError:
            raise
        return {
            "manifest": result.manifest.model_dump(mode="json"),
            "cache_stats": {
                "hits": result.cache_stats.hits,
                "misses": result.cache_stats.misses,
            },
        }

    try:
        job = runner.submit(
            _invoke,
            metadata={
                "pipeline_id": pipeline.id,
                "mode": pipeline.mode,
                "graph_hash": pipeline.graph_hash(),
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return _to_record(job)


@router.get("", summary="List recent runs (in-memory)")
async def list_runs(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    runner = _get_runner(request)
    # Narrow the literal-check so the jobs module does not get tricked
    # into seeing a free-form string as a JobStatus.
    allowed_status = {"queued", "running", "success", "error", "cancelled"}
    status_arg = status_filter if status_filter in allowed_status else None
    rows, total = runner.list(limit=limit, offset=offset, status=status_arg)  # type: ignore[arg-type]
    return {
        "items": [_to_record(r).model_dump(mode="json") for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{run_id}",
    summary="Run status",
    response_model=RunResponse,
)
async def get_run(request: Request, run_id: str) -> RunResponse:
    runner = _get_runner(request)
    job = runner.get(run_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run {run_id!r} not found",
        )
    return _to_record(job)


@router.get("/{run_id}/manifest", summary="Full run manifest")
async def get_run_manifest(request: Request, run_id: str) -> dict[str, Any]:
    runner = _get_runner(request)
    job = runner.get(run_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run {run_id!r} not found",
        )
    if job.status != "success":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"run {run_id!r} is {job.status!r}; no manifest available yet",
        )
    payload = job.result
    if not isinstance(payload, dict):  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="job result did not carry a manifest",
        )
    return payload


@router.delete(
    "/{run_id}",
    summary="Cancel a queued / running run",
    status_code=status.HTTP_200_OK,
    response_model=RunResponse,
)
async def cancel_run(request: Request, run_id: str) -> RunResponse:
    runner = _get_runner(request)
    job = runner.get(run_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run {run_id!r} not found",
        )
    runner.cancel(run_id)
    # Re-fetch to reflect the new status.
    refreshed = runner.get(run_id)
    assert refreshed is not None
    return _to_record(refreshed)
