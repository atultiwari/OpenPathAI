"""Heatmap computation + DZI overlay (Phase 21).

A heatmap is a per-class probability map computed by the existing
analyse path (synthetic fallback honoured) for each tile of a
registered slide. It is stored as its own DZI pyramid so OpenSeadragon
can layer it on top of the slide pyramid via a second Tiled-Image
source.

Endpoints
---------

* ``POST   /v1/heatmaps``                                   — compute a heatmap.
* ``GET    /v1/heatmaps``                                   — list heatmaps (optionally per slide).
* ``GET    /v1/heatmaps/{heatmap_id}``                      — heatmap metadata.
* ``DELETE /v1/heatmaps/{heatmap_id}``                      — drop heatmap.
* ``GET    /v1/heatmaps/{heatmap_id}.dzi``                  — DZI descriptor.
* ``GET    /v1/heatmaps/{heatmap_id}_files/{lvl}/{c_r}.png`` — DZI tile bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from openpathai.io.wsi import open_slide
from openpathai.server.auth import AuthDependency
from openpathai.server.dzi import (
    DEFAULT_OVERLAP,
    DEFAULT_TILE_SIZE,
    DziPyramid,
    ensure_pyramid_root,
)

__all__ = ["ComputeHeatmapRequest", "HeatmapSummary", "router"]


router = APIRouter(prefix="/heatmaps", tags=["heatmaps"], dependencies=[AuthDependency])


_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{6,128}$")
_TILE_PATH = re.compile(r"^(?P<level>\d+)/(?P<col>\d+)_(?P<row>\d+)\.png$")


class ComputeHeatmapRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    slide_id: str = Field(min_length=8)
    model_name: str = Field(default="heuristic-synthetic", min_length=1)
    classes: tuple[str, ...] = Field(default=("class_0", "class_1"), min_length=1)
    tile_grid: int = Field(default=8, ge=2, le=64)
    """Number of cells along the longer slide axis. Each cell becomes
    one heatmap pixel before pyramidisation."""


class HeatmapSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    heatmap_id: str
    slide_id: str
    model_name: str
    resolved_model_name: str
    classes: tuple[str, ...]
    fallback_reason: str | None
    width: int
    height: int
    dzi_url: str
    tile_url_template: str


def _slides_root(request: Request) -> Path:
    return request.app.state.settings.openpathai_home / "slides"


def _heatmaps_root(request: Request) -> Path:
    root = request.app.state.settings.openpathai_home / "heatmaps"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _dzi_root(request: Request) -> Path:
    root = request.app.state.settings.openpathai_home / "heatmap-dzi"
    return ensure_pyramid_root(root)


def _safe(heatmap_id: str) -> str:
    if not _SAFE_ID.match(heatmap_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid heatmap id {heatmap_id!r}",
        )
    return heatmap_id


def _meta_path(root: Path, heatmap_id: str) -> Path:
    return root / heatmap_id / "meta.json"


def _read_meta(root: Path, heatmap_id: str) -> dict[str, Any] | None:
    p = _meta_path(root, heatmap_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _slide_meta(request: Request, slide_id: str) -> dict[str, Any]:
    sroot = _slides_root(request)
    p = sroot / slide_id / "meta.json"
    if not p.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"slide {slide_id!r} not found",
        )
    return json.loads(p.read_text(encoding="utf-8"))


def _heatmap_array(
    request: Request,
    body: ComputeHeatmapRequest,
    slide_meta: dict[str, Any],
) -> tuple[np.ndarray, str, str | None]:
    """Compute a low-res H x W x 3 RGB array representing the heatmap.

    The array is built from per-cell class probabilities; the dominant
    class index drives the hue, the confidence drives the alpha-blended
    intensity so OpenSeadragon's overlay reads naturally.

    Returns ``(rgb_uint8, resolved_model_name, fallback_reason)``.
    """
    grid = body.tile_grid
    source_path = Path(slide_meta["source_path"])
    with open_slide(source_path) as slide:
        info = slide.info
    longer = max(info.width, info.height, 1)
    aspect = info.width / longer, info.height / longer
    cells_w = max(2, round(grid * aspect[0]))
    cells_h = max(2, round(grid * aspect[1]))

    resolved, fallback = _resolve_model(body.model_name)

    # Deterministic per-cell class probabilities. Hash anchors avoid a
    # mutable `random.seed()` and keep tests reproducible.
    palette = _class_palette(len(body.classes))
    rgb = np.zeros((cells_h, cells_w, 3), dtype=np.uint8)
    seed_bytes = hashlib.sha256(
        f"{body.slide_id}:{body.model_name}".encode()
    ).digest()
    rng = np.random.default_rng(int.from_bytes(seed_bytes[:8], "big"))
    raw_logits = rng.standard_normal((cells_h, cells_w, len(body.classes)))
    probs = np.exp(raw_logits - raw_logits.max(axis=-1, keepdims=True))
    probs = probs / probs.sum(axis=-1, keepdims=True)
    top_class = probs.argmax(axis=-1)
    top_conf = probs.max(axis=-1)
    rgb[..., :] = palette[top_class]
    intensity = (top_conf * 255).clip(0, 255).astype(np.uint8)
    rgb = np.where(intensity[..., None] > 0, rgb, 0)
    rgb = (rgb.astype(np.float32) * (intensity[..., None] / 255.0)).clip(0, 255).astype(
        np.uint8
    )
    return rgb, resolved, fallback


def _resolve_model(model_name: str) -> tuple[str, str | None]:
    """Return ``(resolved_model_name, fallback_reason)``.

    The heatmap path is happy with a synthetic answer — the iron-rule
    contract ('no silent fallbacks') is met by surfacing the
    ``fallback_reason`` on the wire.
    """
    if model_name.endswith("-synthetic"):
        return model_name, "explicit_synthetic_request"
    try:
        import torch  # noqa: F401

        from openpathai.models.registry import default_model_registry
    except Exception:
        return f"{model_name}-synthetic", "torch_unavailable"
    try:
        registry = default_model_registry()
        registry.get(model_name)
    except Exception:
        return f"{model_name}-synthetic", "model_not_in_registry"
    # Heatmap inference still synthesises today — Phase 22 will swap in
    # a tile-by-tile real forward pass. The contract: the wire makes
    # the reality of the data explicit.
    return f"{model_name}-synthetic", "real_heatmap_path_pending"


def _class_palette(n: int) -> np.ndarray:
    """Stable per-class colour palette (n x 3 uint8)."""
    base = np.array(
        [
            [220, 50, 50],
            [50, 130, 220],
            [60, 180, 100],
            [220, 200, 60],
            [180, 80, 200],
            [50, 200, 200],
            [240, 130, 60],
            [120, 120, 200],
        ],
        dtype=np.uint8,
    )
    if n <= base.shape[0]:
        return base[:n]
    repeats = int(np.ceil(n / base.shape[0]))
    return np.tile(base, (repeats, 1))[:n]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Compute a heatmap for a slide",
    response_model=HeatmapSummary,
)
async def compute_heatmap(
    request: Request, body: ComputeHeatmapRequest
) -> HeatmapSummary:
    slide_meta = _slide_meta(request, body.slide_id)
    rgb, resolved, fallback = _heatmap_array(request, body, slide_meta)
    height, width = rgb.shape[:2]
    digest = hashlib.sha256(
        f"{body.slide_id}|{body.model_name}|{','.join(body.classes)}".encode()
        + rgb.tobytes()[:512]
    ).hexdigest()[:24]
    heatmap_id = f"hm_{digest}"
    meta = {
        "heatmap_id": heatmap_id,
        "slide_id": body.slide_id,
        "model_name": body.model_name,
        "resolved_model_name": resolved,
        "fallback_reason": fallback,
        "classes": list(body.classes),
        "tile_grid": body.tile_grid,
        "width": int(width),
        "height": int(height),
    }
    root = _heatmaps_root(request)
    (root / heatmap_id).mkdir(parents=True, exist_ok=True)
    _meta_path(root, heatmap_id).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    # Materialise pyramid eagerly so the viewer's first DZI request is
    # cheap. This is small (cells_h x cells_w <= 64**2) so the cost is a
    # few milliseconds.
    pyramid = DziPyramid(
        _dzi_root(request),
        heatmap_id,
        array=rgb,
        tile_size=DEFAULT_TILE_SIZE,
        overlap=DEFAULT_OVERLAP,
    )
    pyramid.descriptor_path()
    return HeatmapSummary(
        heatmap_id=heatmap_id,
        slide_id=body.slide_id,
        model_name=body.model_name,
        resolved_model_name=resolved,
        classes=tuple(body.classes),
        fallback_reason=fallback,
        width=int(width),
        height=int(height),
        dzi_url=f"/v1/heatmaps/{heatmap_id}.dzi",
        tile_url_template=(
            f"/v1/heatmaps/{heatmap_id}_files/{{level}}/{{col}}_{{row}}.png"
        ),
    )


@router.get("", summary="List heatmaps")
async def list_heatmaps(
    request: Request,
    slide_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    root = _heatmaps_root(request)
    items: list[dict[str, Any]] = []
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            meta = _read_meta(root, entry.name)
            if meta is None:
                continue
            if slide_id and meta.get("slide_id") != slide_id:
                continue
            items.append(meta)
    total = len(items)
    return {
        "items": items[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{heatmap_id}.dzi",
    summary="DZI descriptor",
    responses={200: {"content": {"application/xml": {}}}},
)
async def get_dzi_descriptor(request: Request, heatmap_id: str) -> Response:
    hid = _safe(heatmap_id)
    root = _heatmaps_root(request)
    meta = _read_meta(root, hid)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"heatmap {hid!r} not found",
        )
    pyramid = _pyramid_for(request, hid, meta)
    body = pyramid.descriptor_path().read_bytes()
    return Response(content=body, media_type="application/xml")


@router.get(
    "/{heatmap_id}_files/{tile_path:path}",
    summary="DZI tile bytes",
    responses={200: {"content": {"image/png": {}}}},
)
async def get_dzi_tile(
    request: Request, heatmap_id: str, tile_path: str
) -> Response:
    hid = _safe(heatmap_id)
    match = _TILE_PATH.match(tile_path)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid tile path {tile_path!r}",
        )
    root = _heatmaps_root(request)
    meta = _read_meta(root, hid)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"heatmap {hid!r} not found",
        )
    pyramid = _pyramid_for(request, hid, meta)
    try:
        body = pyramid.tile_bytes(
            int(match.group("level")),
            int(match.group("col")),
            int(match.group("row")),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return Response(content=body, media_type="image/png")


@router.get(
    "/{heatmap_id}",
    summary="Heatmap metadata",
    response_model=HeatmapSummary,
)
async def get_heatmap(request: Request, heatmap_id: str) -> HeatmapSummary:
    hid = _safe(heatmap_id)
    meta = _read_meta(_heatmaps_root(request), hid)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"heatmap {hid!r} not found",
        )
    return HeatmapSummary(
        heatmap_id=meta["heatmap_id"],
        slide_id=meta["slide_id"],
        model_name=meta["model_name"],
        resolved_model_name=meta["resolved_model_name"],
        classes=tuple(meta["classes"]),
        fallback_reason=meta.get("fallback_reason"),
        width=int(meta["width"]),
        height=int(meta["height"]),
        dzi_url=f"/v1/heatmaps/{hid}.dzi",
        tile_url_template=f"/v1/heatmaps/{hid}_files/{{level}}/{{col}}_{{row}}.png",
    )


@router.delete(
    "/{heatmap_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a heatmap and its pyramid",
)
async def delete_heatmap(request: Request, heatmap_id: str) -> None:
    hid = _safe(heatmap_id)
    root = _heatmaps_root(request)
    if not (root / hid).is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"heatmap {hid!r} not found",
        )
    shutil.rmtree(root / hid, ignore_errors=True)
    pyramid_dir = _dzi_root(request) / hid
    if pyramid_dir.is_dir():
        shutil.rmtree(pyramid_dir, ignore_errors=True)


def _pyramid_for(
    request: Request, heatmap_id: str, meta: dict[str, Any]
) -> DziPyramid:
    """Reconstruct the in-memory pyramid backing for a heatmap.

    The heatmap RGB bytes live alongside the meta as a tiny PNG; we
    reload it on demand so a server restart still serves DZI tiles.
    """
    arr_path = _heatmaps_root(request) / heatmap_id / "heatmap.png"
    if arr_path.is_file():
        from PIL import Image

        with Image.open(arr_path) as img:
            arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    else:
        # First-time path — reconstruct from meta + slide. Cheap because
        # _heatmap_array is deterministic.
        slide_meta = _slide_meta(request, meta["slide_id"])
        body = ComputeHeatmapRequest(
            slide_id=meta["slide_id"],
            model_name=meta["model_name"],
            classes=tuple(meta["classes"]),
            tile_grid=int(meta.get("tile_grid", 8)),
        )
        arr, _, _ = _heatmap_array(request, body, slide_meta)
        from PIL import Image

        Image.fromarray(arr, mode="RGB").save(arr_path, format="PNG")
    return DziPyramid(
        _dzi_root(request),
        heatmap_id,
        array=arr,
        tile_size=DEFAULT_TILE_SIZE,
        overlap=DEFAULT_OVERLAP,
    )
