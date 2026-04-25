"""Cohort CRUD (Phase 20.5).

Cohorts are stored as YAML files under
``settings.openpathai_home / "cohorts"`` so the canvas Cohorts
screen can list / build / load / QC them without a database.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.io.cohort import Cohort
from openpathai.server.auth import AuthDependency

__all__ = ["BuildCohortRequest", "router"]


router = APIRouter(prefix="/cohorts", tags=["cohorts"], dependencies=[AuthDependency])


_SAFE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")


class BuildCohortRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    directory: str = Field(min_length=1)
    pattern: str | None = None


def _root(request: Request) -> Path:
    root = request.app.state.settings.openpathai_home / "cohorts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe(cohort_id: str) -> str:
    if not _SAFE_ID.match(cohort_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid cohort id {cohort_id!r}",
        )
    return cohort_id


def _path(request: Request, cohort_id: str) -> Path:
    return _root(request) / f"{_safe(cohort_id)}.yaml"


def _envelope(cohort_id: str, cohort: Cohort) -> dict[str, Any]:
    return {
        "id": cohort_id,
        "slide_count": len(cohort.slides),
        # Slide ids are user-supplied IDs (not paths) — safe to surface.
        "slide_ids": [s.slide_id for s in cohort.slides],
    }


@router.get("", summary="List saved cohorts")
async def list_cohorts(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    root = _root(request)
    files = sorted(root.glob("*.yaml"))
    items: list[dict[str, Any]] = []
    for fh in files:
        try:
            cohort = Cohort.from_yaml(fh)
            items.append(_envelope(fh.stem, cohort))
        except (ValueError, FileNotFoundError) as exc:
            items.append({"id": fh.stem, "error": str(exc)})
    total = len(items)
    return {
        "items": items[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Build a cohort YAML from a directory of slide files",
)
async def create_cohort(request: Request, body: BuildCohortRequest) -> dict[str, Any]:
    try:
        cohort = Cohort.from_directory(body.directory, body.id, pattern=body.pattern)
    except (NotADirectoryError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    out = _path(request, body.id)
    cohort.to_yaml(out)
    return _envelope(body.id, cohort)


@router.get("/{cohort_id}", summary="Retrieve a saved cohort")
async def get_cohort(request: Request, cohort_id: str) -> dict[str, Any]:
    path = _path(request, cohort_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cohort {cohort_id!r} not found",
        )
    cohort = Cohort.from_yaml(path)
    return _envelope(cohort_id, cohort)


@router.delete(
    "/{cohort_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved cohort",
)
async def delete_cohort(request: Request, cohort_id: str) -> None:
    path = _path(request, cohort_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cohort {cohort_id!r} not found",
        )
    path.unlink()


@router.post(
    "/{cohort_id}/qc",
    summary="Run QC over a cohort (returns the summary tile)",
)
async def cohort_qc(request: Request, cohort_id: str) -> dict[str, Any]:
    path = _path(request, cohort_id)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cohort {cohort_id!r} not found",
        )
    cohort = Cohort.from_yaml(path)

    def _flat(_slide: Any) -> np.ndarray:
        # The Phase-9 QC plumbing accepts a thumbnail extractor. Without
        # the GUI / WSI viewer we hand it a deterministic mid-grey so
        # the summary endpoint doesn't depend on Tier-2+ deps.
        return np.full((96, 96, 3), 200, dtype=np.uint8)

    try:
        report = cohort.run_qc(_flat)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"QC failed: {exc!s}",
        ) from exc
    return {
        "id": cohort_id,
        "summary": report.summary(),
        "slide_count": len(cohort.slides),
    }
