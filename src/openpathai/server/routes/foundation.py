"""Foundation-backed endpoints (Phase 21.9 chunk B).

Currently exposes one route — ``POST /v1/foundation/embed-folder`` —
which walks an on-disk image folder, runs every tile through the
chosen foundation backbone's ``.embed()`` method, and writes the
resulting matrix as parquet (or CSV) under
``$OPENPATHAI_HOME/embeddings/<run_id>/embeddings.<ext>``.

The route honours the iron-rule-#11 fallback resolver — if the
requested backbone isn't installable (gated, missing weight, etc.)
the run is rejected with a structured envelope so the wizard can
surface the recovery path inline.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency

__all__ = ["EmbedFolderRequest", "EmbedFolderResult", "router"]


router = APIRouter(prefix="/foundation", tags=["foundation"], dependencies=[AuthDependency])


_TILE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
_DEFAULT_TILE_CAP = 1000


class EmbedFolderRequest(BaseModel):
    """``POST /v1/foundation/embed-folder`` payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_folder: str = Field(min_length=1)
    backbone: str = Field(default="dinov2_vits14", min_length=1)
    output_format: str = Field(default="parquet")  # "parquet" | "csv"
    tile_cap: int = Field(default=_DEFAULT_TILE_CAP, ge=1, le=10_000)


class EmbedFolderResult(BaseModel):
    """Wire shape for the embed-folder endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    source_folder: str
    output_path: str
    output_format: str
    tiles: int
    embedding_dim: int
    backbone: str
    resolved_backbone_id: str
    fallback_reason: str
    message: str | None = None
    install_cmd: str | None = None


def _embeddings_root() -> Path:
    return Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai")) / "embeddings"


def _scan_tiles(folder: Path, *, cap: int) -> list[Path]:
    out: list[Path] = []
    for child in sorted(folder.rglob("*")):
        if child.is_file() and child.suffix.lower() in _TILE_EXTS:
            out.append(child)
            if len(out) >= cap:
                break
    return out


@router.post(
    "/embed-folder",
    summary="Run a foundation backbone over every tile in a folder; write embeddings.",
    response_model=EmbedFolderResult,
)
async def embed_folder(body: EmbedFolderRequest) -> EmbedFolderResult:
    folder = Path(body.source_folder).expanduser()
    if not folder.is_dir():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"source_folder {body.source_folder!r} is not a directory.",
        )

    try:
        import numpy as np
        import torch
        from PIL import Image

        from openpathai.foundation.fallback import (
            build_resolved_adapter,
            resolve_backbone,
        )
        from openpathai.foundation.registry import default_foundation_registry
    except ImportError as exc:
        return EmbedFolderResult(
            run_id="-",
            source_folder=str(folder),
            output_path="-",
            output_format=body.output_format,
            tiles=0,
            embedding_dim=0,
            backbone=body.backbone,
            resolved_backbone_id=body.backbone,
            fallback_reason="missing_backend",
            message=f"required runtime missing: {exc}",
            install_cmd="uv sync --extra train --extra data",
        )

    try:
        registry = default_foundation_registry()
        decision = resolve_backbone(body.backbone, registry=registry)
        adapter = build_resolved_adapter(decision, registry=registry)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"could not build backbone {body.backbone!r}: {exc}",
        ) from exc

    tiles = _scan_tiles(folder, cap=body.tile_cap)
    if not tiles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"No image files found under {folder}. Expected one of: {', '.join(_TILE_EXTS)}."
            ),
        )

    run_id = uuid4().hex
    out_dir = _embeddings_root() / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    fmt = body.output_format if body.output_format in {"parquet", "csv"} else "parquet"

    embeddings: list[Any] = []
    paths: list[str] = []
    for tile_path in tiles:
        with Image.open(tile_path) as raw:
            arr = np.asarray(raw.convert("RGB"), dtype=np.uint8)
        with torch.no_grad():
            features = adapter.embed(arr)
        embeddings.append(np.asarray(features).reshape(-1))
        paths.append(str(tile_path))

    matrix = np.stack(embeddings).astype(np.float32, copy=False)
    embedding_dim = int(matrix.shape[1]) if matrix.ndim == 2 else int(matrix.shape[-1])

    if fmt == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            fmt = "csv"
        else:
            table = pa.table(
                {
                    "path": paths,
                    **{f"e{i}": matrix[:, i].tolist() for i in range(embedding_dim)},
                }
            )
            output_path = out_dir / "embeddings.parquet"
            pq.write_table(table, output_path)

    if fmt == "csv":
        output_path = out_dir / "embeddings.csv"
        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["path"] + [f"e{i}" for i in range(embedding_dim)])
            for path, row in zip(paths, matrix.tolist(), strict=False):
                writer.writerow([path, *row])

    return EmbedFolderResult(
        run_id=run_id,
        source_folder=str(folder),
        output_path=str(output_path),
        output_format=fmt,
        tiles=len(tiles),
        embedding_dim=embedding_dim,
        backbone=body.backbone,
        resolved_backbone_id=decision.resolved_id,
        fallback_reason=decision.reason,
    )
