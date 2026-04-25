"""Dataset card registry (Phase 19) + custom-folder register (Phase 20.5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency

__all__ = ["RegisterFolderRequest", "router"]


class RegisterFolderRequest(BaseModel):
    """``POST /v1/datasets/register`` payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tissue: tuple[str, ...] = Field(min_length=1)
    classes: tuple[str, ...] | None = None
    display_name: str | None = None
    license: str = "user-supplied"
    stain: str = "H&E"
    overwrite: bool = False


router = APIRouter(
    prefix="/datasets",
    tags=["datasets"],
    dependencies=[AuthDependency],
)


def _dump_card(card: Any) -> dict[str, Any]:
    payload = card.model_dump(mode="json")
    # Card ships local_path + other fs paths through DatasetDownload;
    # the PHI middleware already rewrites /Users/… style absolutes, but
    # drop the raw ``local_path`` field explicitly for defence-in-depth.
    source = payload.get("source")
    if isinstance(source, dict) and "local_path" in source:
        source["local_path"] = None
    return payload


@router.get("", summary="List dataset cards")
async def list_datasets(
    q: str | None = Query(default=None, description="Substring filter on id"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    from openpathai.data.registry import default_registry

    reg = default_registry()
    names = sorted(reg.names())
    if q:
        needle = q.lower()
        names = [n for n in names if needle in n.lower()]
    total = len(names)
    page_names = names[offset : offset + limit]
    items = [_dump_card(reg.get(n)) for n in page_names]
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{dataset_id}", summary="Retrieve one dataset card")
async def get_dataset(dataset_id: str) -> dict[str, Any]:
    from openpathai.data.registry import default_registry

    reg = default_registry()
    try:
        card = reg.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown dataset {dataset_id!r}",
        ) from exc
    return _dump_card(card)


@router.post(
    "/register",
    summary="Register a folder of class-named subfolders as a tile dataset",
    status_code=status.HTTP_201_CREATED,
)
async def register_folder(body: RegisterFolderRequest) -> dict[str, Any]:
    """Thin wrapper over :func:`openpathai.data.local.register_folder`.

    The folder layout is ``<path>/<class_name>/<image>.png`` (Phase 7).
    Returns the registered :class:`DatasetCard` payload.
    """
    from openpathai.data.local import register_folder as _register

    try:
        card = _register(
            body.path,
            name=body.name,
            tissue=list(body.tissue),
            classes=list(body.classes) if body.classes else None,
            display_name=body.display_name,
            license=body.license,
            stain=body.stain,
            overwrite=body.overwrite,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (NotADirectoryError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _dump_card(card)
