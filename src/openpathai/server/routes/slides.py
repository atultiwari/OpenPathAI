"""Slide upload + DZI tile serving (Phase 21).

Endpoints
---------

* ``POST   /v1/slides``                                — multipart upload of a slide file.
* ``GET    /v1/slides``                                — list registered slides (paged).
* ``GET    /v1/slides/{slide_id}``                     — slide metadata.
* ``DELETE /v1/slides/{slide_id}``                     — drop slide + pyramid.
* ``GET    /v1/slides/{slide_id}.dzi``                 — DZI descriptor.
* ``GET    /v1/slides/{slide_id}_files/{lvl}/{c_r}.{ext}`` — DZI tile bytes.

Slides are written under ``$OPENPATHAI_HOME/slides/<sha256>/`` — sha256
of the source bytes is the slide id, so re-uploading the same file is a
no-op (and shares the cached pyramid).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from openpathai.io.wsi import open_slide
from openpathai.server.auth import AuthDependency
from openpathai.server.dzi import (
    DEFAULT_OVERLAP,
    DEFAULT_TILE_SIZE,
    DziPyramid,
    ensure_pyramid_root,
    hash_file,
)

__all__ = ["SlideSummary", "router"]


router = APIRouter(prefix="/slides", tags=["slides"], dependencies=[AuthDependency])


_SAFE_ID = re.compile(r"^[a-f0-9]{8,64}$")
_TILE_PATH = re.compile(r"^(?P<level>\d+)/(?P<col>\d+)_(?P<row>\d+)\.(?P<ext>png|jpg|jpeg)$")
_ALLOWED_TILE_EXT = {"png"}


class SlideSummary(BaseModel):
    """Wire shape of a registered slide."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slide_id: str
    filename: str
    size_bytes: int
    width: int
    height: int
    mpp: float | None
    level_count: int
    backend: str
    dzi_url: str
    tile_url_template: str


def _slides_root(request: Request) -> Path:
    root = request.app.state.settings.openpathai_home / "slides"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _dzi_root(request: Request) -> Path:
    root = request.app.state.settings.openpathai_home / "dzi"
    return ensure_pyramid_root(root)


def _meta_path(root: Path, slide_id: str) -> Path:
    return root / slide_id / "meta.json"


def _safe(slide_id: str) -> str:
    if not _SAFE_ID.match(slide_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid slide id {slide_id!r}",
        )
    return slide_id


def _build_summary(meta: dict[str, Any]) -> SlideSummary:
    sid = meta["slide_id"]
    return SlideSummary(
        slide_id=sid,
        filename=meta["filename"],
        size_bytes=int(meta["size_bytes"]),
        width=int(meta["width"]),
        height=int(meta["height"]),
        mpp=meta.get("mpp"),
        level_count=int(meta.get("level_count", 1)),
        backend=str(meta.get("backend", "pillow")),
        dzi_url=f"/v1/slides/{sid}.dzi",
        tile_url_template=f"/v1/slides/{sid}_files/{{level}}/{{col}}_{{row}}.png",
    )


def _read_meta(root: Path, slide_id: str) -> dict[str, Any] | None:
    p = _meta_path(root, slide_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _pyramid(request: Request, slide_id: str) -> DziPyramid:
    root = _slides_root(request)
    meta = _read_meta(root, slide_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"slide {slide_id!r} not found",
        )
    source_path = Path(meta["source_path"])
    return DziPyramid(
        _dzi_root(request),
        slide_id,
        source_path=source_path,
        tile_size=DEFAULT_TILE_SIZE,
        overlap=DEFAULT_OVERLAP,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a slide and register it for the viewer",
    response_model=SlideSummary,
)
async def upload_slide(
    request: Request,
    file: UploadFile = File(...),
    filename: str | None = Form(default=None),
) -> SlideSummary:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty upload")
    name = filename or (file.filename or "slide.tif")
    safe_name = Path(name).name  # strip any client-supplied directory parts.
    root = _slides_root(request)
    # Hash to a content-addressable id.
    import hashlib

    sid = hashlib.sha256(raw).hexdigest()
    slide_dir = root / sid
    slide_dir.mkdir(parents=True, exist_ok=True)
    source_path = slide_dir / safe_name
    if not source_path.is_file():
        source_path.write_bytes(raw)
    # Probe with the WSI reader. Bail early if the file is not openable.
    try:
        with open_slide(source_path) as slide:
            info = slide.info
        meta: dict[str, Any] = {
            "slide_id": sid,
            "filename": safe_name,
            "source_path": str(source_path),
            "size_bytes": len(raw),
            "width": info.width,
            "height": info.height,
            "mpp": info.mpp,
            "level_count": info.level_count,
            "backend": str(info.backend.value),
        }
    except Exception as exc:
        # Roll back on a bad upload so callers see a clean state.
        shutil.rmtree(slide_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"slide could not be opened: {exc!s}",
        ) from exc
    _meta_path(root, sid).parent.mkdir(parents=True, exist_ok=True)
    _meta_path(root, sid).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # Pre-build the descriptor so the viewer's first DZI request is hot.
    pyramid = DziPyramid(_dzi_root(request), sid, source_path=source_path)
    pyramid.descriptor_path()
    return _build_summary(meta)


@router.get("", summary="List registered slides")
async def list_slides(
    request: Request,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be in [1, 500]",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be >= 0",
        )
    root = _slides_root(request)
    items: list[dict[str, Any]] = []
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            meta = _read_meta(root, entry.name)
            if meta is None:
                continue
            items.append(_build_summary(meta).model_dump(mode="json"))
    total = len(items)
    return {
        "items": items[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{slide_id}.dzi",
    summary="DZI descriptor",
    responses={200: {"content": {"application/xml": {}}}},
)
async def get_dzi_descriptor(request: Request, slide_id: str) -> Response:
    sid = _safe(slide_id)
    pyramid = _pyramid(request, sid)
    body = pyramid.descriptor_path().read_bytes()
    return Response(content=body, media_type="application/xml")


@router.get(
    "/{slide_id}_files/{tile_path:path}",
    summary="DZI tile bytes",
    responses={200: {"content": {"image/png": {}}}},
)
async def get_dzi_tile(request: Request, slide_id: str, tile_path: str) -> Response:
    sid = _safe(slide_id)
    match = _TILE_PATH.match(tile_path)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid tile path {tile_path!r}",
        )
    ext = match.group("ext").lower()
    if ext not in _ALLOWED_TILE_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported tile extension {ext!r}",
        )
    pyramid = _pyramid(request, sid)
    try:
        body = pyramid.tile_bytes(
            int(match.group("level")),
            int(match.group("col")),
            int(match.group("row")),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(content=body, media_type="image/png")


@router.get(
    "/{slide_id}",
    summary="Slide metadata",
    response_model=SlideSummary,
)
async def get_slide(request: Request, slide_id: str) -> SlideSummary:
    sid = _safe(slide_id)
    meta = _read_meta(_slides_root(request), sid)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"slide {sid!r} not found",
        )
    return _build_summary(meta)


@router.delete(
    "/{slide_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a slide and its pyramid",
)
async def delete_slide(request: Request, slide_id: str) -> None:
    sid = _safe(slide_id)
    root = _slides_root(request)
    meta = _read_meta(root, sid)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"slide {sid!r} not found",
        )
    shutil.rmtree(root / sid, ignore_errors=True)
    pyramid = DziPyramid(_dzi_root(request), sid, source_path=Path(meta["source_path"]))
    pyramid.remove()


def _content_address_from(raw: bytes) -> str:
    """Convenience for tests — re-export the hashing rule."""
    import hashlib

    return hashlib.sha256(raw).hexdigest()


__all__ += ["_content_address_from", "hash_file"]
