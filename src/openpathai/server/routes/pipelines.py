"""Pipeline CRUD (Phase 19).

Pipelines are stored as YAML files under
``settings.resolved_pipelines_dir()``. The wire format is JSON —
the :class:`openpathai.pipeline.executor.Pipeline` pydantic model
round-trips losslessly between the two. Validation rejects
pipelines that reference unknown nodes or form cycles.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from openpathai.pipeline.executor import Pipeline
from openpathai.pipeline.node import REGISTRY as NODE_REGISTRY
from openpathai.server.auth import AuthDependency

__all__ = ["PipelineEnvelope", "PipelineValidationReport", "router"]


router = APIRouter(
    prefix="/pipelines",
    tags=["pipelines"],
    dependencies=[AuthDependency],
)


_SAFE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")


class PipelineEnvelope(BaseModel):
    """Wire shape for a saved pipeline on disk."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    pipeline: dict[str, Any]
    graph_hash: str


class PipelineValidationReport(BaseModel):
    """Result of ``POST /v1/pipelines/validate``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    errors: list[str] = Field(default_factory=list)
    graph_hash: str | None = None
    unknown_ops: list[str] = Field(default_factory=list)


def _pipelines_root(request: Request) -> Path:
    root = request.app.state.settings.resolved_pipelines_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_id(pipeline_id: str) -> str:
    if not _SAFE_ID.match(pipeline_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"invalid pipeline id {pipeline_id!r}; must match [A-Za-z_][A-Za-z0-9_-]*"),
        )
    return pipeline_id


def _path_for(request: Request, pipeline_id: str) -> Path:
    return _pipelines_root(request) / f"{_safe_id(pipeline_id)}.yaml"


def _validate_pipeline(payload: dict[str, Any]) -> PipelineValidationReport:
    try:
        pipeline = Pipeline.model_validate(payload)
    except ValidationError as exc:
        return PipelineValidationReport(
            valid=False,
            errors=[
                f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in exc.errors()
            ],
        )
    unknown = sorted({step.op for step in pipeline.steps if not NODE_REGISTRY.has(step.op)})
    if unknown:
        return PipelineValidationReport(
            valid=False,
            errors=[f"unknown op: {op}" for op in unknown],
            unknown_ops=unknown,
        )
    return PipelineValidationReport(
        valid=True,
        graph_hash=pipeline.graph_hash(),
    )


@router.get("", summary="List saved pipelines")
async def list_pipelines(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    root = _pipelines_root(request)
    files = sorted(root.glob("*.yaml"))
    ids = [p.stem for p in files]
    total = len(ids)
    page_ids = ids[offset : offset + limit]
    items: list[dict[str, Any]] = []
    for pid in page_ids:
        try:
            payload = yaml.safe_load((root / f"{pid}.yaml").read_text(encoding="utf-8")) or {}
            pipeline = Pipeline.model_validate(payload)
            items.append(
                PipelineEnvelope(
                    id=pid,
                    pipeline=pipeline.model_dump(mode="json"),
                    graph_hash=pipeline.graph_hash(),
                ).model_dump(mode="json")
            )
        except (ValueError, ValidationError) as exc:
            items.append(
                {
                    "id": pid,
                    "pipeline": None,
                    "graph_hash": None,
                    "error": f"{type(exc).__name__}: {exc!s}",
                }
            )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/{pipeline_id}",
    summary="Retrieve a saved pipeline",
    response_model=PipelineEnvelope,
)
async def get_pipeline(request: Request, pipeline_id: str) -> PipelineEnvelope:
    path = _path_for(request, pipeline_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"pipeline {pipeline_id!r} not found",
        )
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        pipeline = Pipeline.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"stored pipeline is invalid: {exc.errors()}",
        ) from exc
    return PipelineEnvelope(
        id=pipeline_id,
        pipeline=pipeline.model_dump(mode="json"),
        graph_hash=pipeline.graph_hash(),
    )


@router.put(
    "/{pipeline_id}",
    summary="Create or replace a saved pipeline",
    status_code=status.HTTP_200_OK,
    response_model=PipelineEnvelope,
)
async def put_pipeline(
    request: Request,
    pipeline_id: str,
    body: dict[str, Any],
) -> PipelineEnvelope:
    try:
        pipeline = Pipeline.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc
    unknown = [step.op for step in pipeline.steps if not NODE_REGISTRY.has(step.op)]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown ops: {sorted(set(unknown))}",
        )
    path = _path_for(request, pipeline_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(pipeline.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    return PipelineEnvelope(
        id=pipeline_id,
        pipeline=pipeline.model_dump(mode="json"),
        graph_hash=pipeline.graph_hash(),
    )


@router.delete(
    "/{pipeline_id}",
    summary="Delete a saved pipeline",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_pipeline(request: Request, pipeline_id: str) -> None:
    path = _path_for(request, pipeline_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"pipeline {pipeline_id!r} not found",
        )
    path.unlink()


@router.post(
    "/validate",
    summary="Validate a pipeline payload without persisting it",
    response_model=PipelineValidationReport,
)
async def validate_pipeline(body: dict[str, Any]) -> PipelineValidationReport:
    return _validate_pipeline(body)
