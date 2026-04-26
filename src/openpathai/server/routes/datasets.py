"""Dataset card registry (Phase 19) + custom-folder register (Phase 20.5)
+ on-demand download surface (Phase 21.6 chunk B)."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency

__all__ = [
    "AnalyseFolderRequest",
    "AnalyseFolderResult",
    "DatasetDownloadRequest",
    "DatasetDownloadResult",
    "DatasetStatus",
    "RegisterFolderRequest",
    "router",
]


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


class AnalyseFolderRequest(BaseModel):
    """``POST /v1/datasets/analyse`` payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)


class AnalyseFolderClass(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    count: int


class AnalyseFolderResult(BaseModel):
    """``POST /v1/datasets/analyse`` response. Mirrors
    :class:`openpathai.data.analyse.AnalysisReport` so the canvas
    wizard can render the report verbatim and decide whether to
    proceed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    exists: bool
    is_directory: bool
    layout: str
    image_count: int
    class_count: int
    classes: tuple[AnalyseFolderClass, ...] = ()
    extensions: tuple[str, ...] = ()
    hidden_entries: tuple[str, ...] = ()
    non_image_files: tuple[str, ...] = ()
    suggested_root: str | None = None
    warnings: tuple[str, ...] = ()
    truncated: bool = False
    bytes_total: int = 0


class DatasetDownloadRequest(BaseModel):
    """``POST /v1/datasets/{name}/download`` payload.

    The three override fields (Phase 21.6.1) let the wizard work
    around unsupported card methods (e.g. Zenodo when the canonical
    archive is unreachable) or point at a Hugging Face mirror /
    local folder. Priority: local_source_path > override_url >
    override_huggingface_repo > the card's declared download.method.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    subset: int | None = Field(default=None, ge=1)
    allow_patterns: tuple[str, ...] | None = None
    dry_run: bool = False
    override_url: str | None = Field(default=None, min_length=1)
    override_huggingface_repo: str | None = Field(default=None, min_length=1)
    local_source_path: str | None = Field(default=None, min_length=1)


class DatasetDownloadResult(BaseModel):
    """Wire shape for the download endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset: str
    status: str  # downloaded | manual | missing_backend | skipped | error
    method: str
    target_dir: str
    files_written: int = 0
    bytes_written: int | None = None
    message: str | None = None
    extra_required: str | None = None
    # Phase 21.7 chunk C — when the user supplies a local_source_path,
    # the route also calls register_folder() and surfaces the new card
    # name here so the wizard's train step can submit against bytes
    # that actually exist on disk.
    registered_card: str | None = None


class DatasetStatus(BaseModel):
    """``GET /v1/datasets/{name}/status`` — is the dataset on disk?"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset: str
    present: bool
    target_dir: str
    files: int
    bytes: int


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


# Phase 22.0 chunk A — folder analyser. Surfaced *before* register/symlink
# so the wizard can refuse to proceed against a folder that
# register_folder would silently turn into an empty card.
@router.post(
    "/analyse",
    summary="Walk a folder and report its layout / classes / warnings",
    response_model=AnalyseFolderResult,
)
async def analyse_dataset_folder(body: AnalyseFolderRequest) -> AnalyseFolderResult:
    from openpathai.data.analyse import analyse_folder

    report = analyse_folder(body.path)
    return AnalyseFolderResult(
        path=report.path,
        exists=report.exists,
        is_directory=report.is_directory,
        layout=report.layout,
        image_count=report.image_count,
        class_count=report.class_count,
        classes=tuple(AnalyseFolderClass(name=c.name, count=c.count) for c in report.classes),
        extensions=report.extensions,
        hidden_entries=report.hidden_entries,
        non_image_files=report.non_image_files,
        suggested_root=report.suggested_root,
        warnings=report.warnings,
        truncated=report.truncated,
        bytes_total=report.bytes_total,
    )


# ─── Phase 21.6 chunk B — on-demand downloads + status ──────────


def _resolve_dataset_dir(name: str) -> Path:
    """Mirror downloaders.default_download_root() / <name>."""
    from openpathai.data.downloaders import default_download_root

    return default_download_root() / name


def _scan_target_dir(target: Path) -> tuple[int, int]:
    if not target.is_dir():
        return (0, 0)
    files = 0
    total = 0
    for child in target.rglob("*"):
        if child.is_file():
            files += 1
            with contextlib.suppress(OSError):
                total += child.stat().st_size
    return (files, total)


def _extra_for_method(method: str) -> str | None:
    """Map download method → install-time extra users should add."""
    if method == "huggingface":
        return "[train] (transitively pulls huggingface_hub)"
    if method == "kaggle":
        return "[kaggle]"
    if method == "zenodo":
        return "[data] (Phase 9 will land Zenodo support)"
    return None


@router.get(
    "/{dataset_id}/status",
    summary="Report whether a dataset is downloaded and where it lives",
    response_model=DatasetStatus,
)
async def get_dataset_status(dataset_id: str) -> DatasetStatus:
    from openpathai.data.registry import default_registry

    reg = default_registry()
    try:
        card = reg.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown dataset {dataset_id!r}",
        ) from exc
    if card.download.method == "local" and card.download.local_path is not None:
        target = Path(card.download.local_path).expanduser()
    else:
        target = _resolve_dataset_dir(card.name)
    files, bytes_written = _scan_target_dir(target)
    return DatasetStatus(
        dataset=card.name,
        present=files > 0,
        target_dir=str(target),
        files=files,
        bytes=bytes_written,
    )


@router.post(
    "/{dataset_id}/download",
    summary="Download (or surface manual instructions for) a registered dataset",
    response_model=DatasetDownloadResult,
)
async def download_dataset(dataset_id: str, body: DatasetDownloadRequest) -> DatasetDownloadResult:
    from openpathai.data.downloaders import (
        MissingBackendError,
        dispatch_download,
    )
    from openpathai.data.registry import default_registry

    reg = default_registry()
    try:
        card = reg.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown dataset {dataset_id!r}",
        ) from exc

    method = card.download.method
    target_dir = _resolve_dataset_dir(card.name)

    if method == "local":
        local = card.download.local_path
        existing = Path(local).expanduser() if local else target_dir
        files, bytes_written = _scan_target_dir(existing)
        return DatasetDownloadResult(
            dataset=card.name,
            status="downloaded" if files > 0 else "skipped",
            method=method,
            target_dir=str(existing),
            files_written=files,
            bytes_written=bytes_written,
            message="local card — bytes already on disk; nothing to download.",
        )

    if body.dry_run:
        from openpathai.data.downloaders import describe_download

        return DatasetDownloadResult(
            dataset=card.name,
            status="skipped",
            method=method,
            target_dir=str(target_dir),
            message=describe_download(card),
        )

    try:
        result = dispatch_download(
            card,
            subset=body.subset,
            override_url=body.override_url,
            override_huggingface_repo=body.override_huggingface_repo,
            local_source_path=body.local_source_path,
        )
    except MissingBackendError as exc:
        return DatasetDownloadResult(
            dataset=card.name,
            status="missing_backend",
            method=method,
            target_dir=str(target_dir),
            message=str(exc),
            extra_required=_extra_for_method(method),
        )
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    wire_status = "manual" if result.skipped and method == "manual" else "downloaded"

    # Phase 21.7 chunk C — when the user pointed at a local folder, also
    # write a `method='local'` card so the registry exposes the bytes
    # the user just supplied. The new card name is `<original>_local` so
    # the original Zenodo / Kaggle / HF card is preserved untouched.
    registered_card: str | None = None
    if body.local_source_path and result.method == "local":
        try:
            from openpathai.data import registry as _registry_mod
            from openpathai.data.local import register_folder
            from openpathai.data.registry import default_registry

            local_card = register_folder(
                Path(body.local_source_path),
                name=f"{card.name}_local",
                tissue=list(card.tissue),
                # Phase 21.7 chunk C — let register_folder infer classes
                # from the folder layout. Forcing the original card's
                # class list would reject any folder whose subdir names
                # don't match (which is the common case when the user
                # downloaded a slim subset).
                classes=None,
                display_name=(card.display_name or card.name) + " (local source)",
                license=card.license or "user-supplied",
                stain=card.stain or "H&E",
                overwrite=True,
            )
            registered_card = local_card.name
            # Force the next default_registry() call to re-scan disk so
            # the new YAML is visible to other routes (Train) immediately.
            _registry_mod._DEFAULT_REGISTRY = None
            _ = default_registry()
        except Exception as exc:
            # Auto-registration is a convenience — if it fails (e.g. the
            # folder isn't an ImageFolder layout) the symlink is still
            # in place; surface the reason in the message so the user
            # can fall back to manual `Datasets → Register` flow.
            return DatasetDownloadResult(
                dataset=card.name,
                status=wire_status,
                method=result.method,
                target_dir=str(result.target_dir),
                files_written=result.files_written,
                bytes_written=result.bytes_written,
                message=(
                    (result.message or "")
                    + f"\nNote: auto-register as a local card failed: {exc}. "
                    "Use Datasets → Register custom dataset to register manually."
                ),
            )

    return DatasetDownloadResult(
        dataset=card.name,
        status=wire_status,
        method=result.method,
        target_dir=str(result.target_dir),
        files_written=result.files_written,
        bytes_written=result.bytes_written,
        message=result.message,
        registered_card=registered_card,
    )
