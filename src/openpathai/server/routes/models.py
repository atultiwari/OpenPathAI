"""Unified model registry view (Phase 19) + per-model download (Phase 21.8).

Merges the classification zoo (``models/zoo/*.yaml``), the
foundation backbones (Phase 13), the detection adapters (Phase 14),
and the segmentation adapters (Phase 14) into a single flat list.
Each row carries a ``kind`` field so the React canvas can group
them in the palette.

Phase 21.8 chunk B adds three per-model routes:

* ``GET /v1/models/{id}/status`` — is the backbone's weight cache
  populated? Walks the timm / huggingface cache directories.
* ``POST /v1/models/{id}/download`` — calls the adapter's
  ``.build(pretrained=True)`` so timm / huggingface_hub pulls the
  weights and returns the resolved on-disk path + size.
* ``GET /v1/models/{id}/size-estimate`` — queries
  ``huggingface_hub.HfApi.model_info`` to size the repo without
  downloading. Returns ``null`` size when the hub is unreachable
  so the UI can render a "?" instead of crashing.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency

__all__ = [
    "ModelDownloadResult",
    "ModelSizeEstimate",
    "ModelStatus",
    "ModelSummary",
    "router",
]


router = APIRouter(
    prefix="/models",
    tags=["models"],
    dependencies=[AuthDependency],
)


ModelKind = str  # "classifier" | "foundation" | "detection" | "segmentation"


class ModelSummary(BaseModel):
    """Wire shape for one model across any registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    kind: ModelKind
    display_name: str = ""
    license: str | None = None
    gated: bool = False
    citation: str | None = None
    hf_repo: str | None = None
    embedding_dim: int | None = None
    input_size: tuple[int, int] | None = None
    tier_compatibility: tuple[str, ...] = ()


def _classifier_rows() -> list[ModelSummary]:
    from openpathai.models.registry import default_model_registry

    out: list[ModelSummary] = []
    try:
        registry = default_model_registry()
    except Exception:  # pragma: no cover - defensive
        return out
    for name in registry.names():
        card = registry.get(name)
        citation = card.citation.text or card.citation.doi or card.citation.url
        tier_dump = card.tier_compatibility.model_dump()
        tiers = tuple(
            kind for kind, level in tier_dump.items() if isinstance(level, str) and level != "no"
        )
        out.append(
            ModelSummary(
                id=name,
                kind="classifier",
                display_name=card.display_name,
                license=card.source.license,
                gated=bool(card.source.gated),
                citation=citation,
                hf_repo=None,
                embedding_dim=None,
                input_size=card.input_size,
                tier_compatibility=tiers,
            )
        )
    return out


def _foundation_rows() -> list[ModelSummary]:
    from openpathai.foundation.registry import default_foundation_registry

    out: list[ModelSummary] = []
    try:
        registry = default_foundation_registry()
    except Exception:  # pragma: no cover - defensive
        return out
    for adapter_id in registry.names():
        adapter = registry.get(adapter_id)
        out.append(
            ModelSummary(
                id=adapter_id,
                kind="foundation",
                display_name=getattr(adapter, "display_name", ""),
                license=getattr(adapter, "license", None),
                gated=bool(getattr(adapter, "gated", False)),
                citation=getattr(adapter, "citation", None),
                hf_repo=getattr(adapter, "hf_repo", None),
                embedding_dim=getattr(adapter, "embedding_dim", None),
                input_size=getattr(adapter, "input_size", None),
                tier_compatibility=tuple(getattr(adapter, "tier_compatibility", ())),
            )
        )
    return out


def _detection_rows() -> list[ModelSummary]:
    from openpathai.detection.registry import default_detection_registry

    out: list[ModelSummary] = []
    try:
        registry = default_detection_registry()
    except Exception:  # pragma: no cover - defensive
        return out
    for adapter_id in registry.names():
        adapter = registry.get(adapter_id)
        out.append(
            ModelSummary(
                id=adapter_id,
                kind="detection",
                display_name=getattr(adapter, "display_name", ""),
                license=getattr(adapter, "license", None),
                gated=bool(getattr(adapter, "gated", False)),
                citation=getattr(adapter, "citation", None),
                hf_repo=getattr(adapter, "hf_repo", None),
                embedding_dim=None,
                input_size=getattr(adapter, "input_size", None),
                tier_compatibility=tuple(getattr(adapter, "tier_compatibility", ())),
            )
        )
    return out


def _segmentation_rows() -> list[ModelSummary]:
    from openpathai.segmentation.registry import default_segmentation_registry

    out: list[ModelSummary] = []
    try:
        registry = default_segmentation_registry()
    except Exception:  # pragma: no cover - defensive
        return out
    for adapter_id in registry.names():
        adapter = registry.get(adapter_id)
        out.append(
            ModelSummary(
                id=adapter_id,
                kind="segmentation",
                display_name=getattr(adapter, "display_name", ""),
                license=getattr(adapter, "license", None),
                gated=bool(getattr(adapter, "gated", False)),
                citation=getattr(adapter, "citation", None),
                hf_repo=getattr(adapter, "hf_repo", None),
                embedding_dim=None,
                input_size=getattr(adapter, "input_size", None),
                tier_compatibility=tuple(getattr(adapter, "tier_compatibility", ())),
            )
        )
    return out


def _all_rows() -> list[ModelSummary]:
    return _classifier_rows() + _foundation_rows() + _detection_rows() + _segmentation_rows()


@router.get("", summary="List every registered model")
async def list_models(
    kind: ModelKind | None = Query(default=None, description="Filter by kind"),
    q: str | None = Query(default=None, description="Case-insensitive substring filter on id"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    rows = _all_rows()
    if kind:
        rows = [r for r in rows if r.kind == kind]
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r.id.lower()]
    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "items": [r.model_dump(mode="json") for r in page],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{model_id}",
    summary="Retrieve one model by id (searches all kinds)",
    response_model=ModelSummary,
)
async def get_model(model_id: str) -> ModelSummary:
    for row in _all_rows():
        if row.id == model_id:
            return row
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"unknown model {model_id!r}",
    )


# ─── Phase 21.8 chunk B — per-model download + status ────────────


class ModelStatus(BaseModel):
    """Wire shape for ``GET /v1/models/{id}/status``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    present: bool
    target_dir: str | None
    size_bytes: int = 0
    file_count: int = 0
    source: str  # "huggingface" | "timm" | "torch_hub" | "unknown"


class ModelSizeEstimate(BaseModel):
    """Wire shape for ``GET /v1/models/{id}/size-estimate``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    hf_repo: str | None
    size_bytes: int | None = None
    file_count: int | None = None
    reason: str | None = None  # populated when size is null


class ModelDownloadResult(BaseModel):
    """Wire shape for ``POST /v1/models/{id}/download``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    status: str  # downloaded | already_present | gated | missing_backend | error
    target_dir: str | None
    size_bytes: int = 0
    file_count: int = 0
    message: str | None = None
    install_cmd: str | None = None
    resolved_id: str | None = None
    fallback_reason: str | None = None


def _hf_hub_cache_dir() -> Path:
    """Mirror ``huggingface_hub`` resolution without importing it."""
    if hf_home := os.environ.get("HF_HOME"):
        return Path(hf_home) / "hub"
    if xdg := os.environ.get("XDG_CACHE_HOME"):
        return Path(xdg) / "huggingface" / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _scan_dir(path: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) for the tree under ``path``."""
    if not path.is_dir():
        return (0, 0)
    files = 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            files += 1
            with contextlib.suppress(OSError):
                total += child.stat().st_size
    return (files, total)


def _hf_repo_cache_dir(repo: str) -> Path | None:
    """Where huggingface_hub stores ``models--<owner>--<name>``."""
    safe = "models--" + repo.replace("/", "--")
    candidate = _hf_hub_cache_dir() / safe
    return candidate if candidate.is_dir() else None


def _resolve_model_row(model_id: str) -> ModelSummary:
    for row in _all_rows():
        if row.id == model_id:
            return row
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"unknown model {model_id!r}",
    )


def _local_status_for_row(row: ModelSummary) -> ModelStatus:
    """Probe the on-disk cache for ``row`` without touching the network."""
    if row.hf_repo:
        cache = _hf_repo_cache_dir(row.hf_repo)
        if cache is not None:
            files, size = _scan_dir(cache)
            return ModelStatus(
                model_id=row.id,
                present=files > 0,
                target_dir=str(cache),
                size_bytes=size,
                file_count=files,
                source="huggingface",
            )
        return ModelStatus(
            model_id=row.id,
            present=False,
            target_dir=str(_hf_hub_cache_dir() / f"models--{row.hf_repo.replace('/', '--')}"),
            source="huggingface",
        )
    return ModelStatus(
        model_id=row.id,
        present=False,
        target_dir=None,
        source="unknown",
    )


@router.get(
    "/{model_id}/status",
    summary="Report whether a model's weights are cached on disk",
    response_model=ModelStatus,
)
async def get_model_status(model_id: str) -> ModelStatus:
    return _local_status_for_row(_resolve_model_row(model_id))


# Phase 21.9 chunk A2 — process-lifetime cache for HF size lookups so
# even when an adapter doesn't declare ``size_bytes`` we only round-trip
# once per model per server boot.
_SIZE_ESTIMATE_CACHE: dict[str, ModelSizeEstimate] = {}


def _adapter_declared_size(model_id: str) -> int | None:
    """Look up the ``size_bytes`` class attr on the foundation /
    detection / segmentation adapter for ``model_id``. Returns
    ``None`` when the adapter doesn't declare one (or doesn't exist)."""
    for resolver in (_foundation_adapter, _detection_adapter):
        adapter = resolver(model_id)
        if adapter is None:
            continue
        candidate = getattr(adapter, "size_bytes", 0)
        if isinstance(candidate, int) and candidate > 0:
            return candidate
    return None


@router.get(
    "/{model_id}/size-estimate",
    summary="Estimate the on-disk size of a model (adapter-declared first, HF metadata fallback)",
    response_model=ModelSizeEstimate,
)
async def get_model_size_estimate(model_id: str) -> ModelSizeEstimate:
    cached = _SIZE_ESTIMATE_CACHE.get(model_id)
    if cached is not None:
        return cached

    row = _resolve_model_row(model_id)

    # Adapter-declared size — instant, no network. Phase 21.9 chunk A2
    # makes this the primary path so the Models tab paints sizes the
    # moment the rows arrive.
    declared = _adapter_declared_size(model_id)
    if declared is not None:
        result = ModelSizeEstimate(
            model_id=model_id,
            hf_repo=row.hf_repo,
            size_bytes=declared,
            reason="adapter-declared",
        )
        _SIZE_ESTIMATE_CACHE[model_id] = result
        return result

    if not row.hf_repo:
        result = ModelSizeEstimate(
            model_id=model_id,
            hf_repo=None,
            reason="model has no hf_repo declared",
        )
        _SIZE_ESTIMATE_CACHE[model_id] = result
        return result

    try:
        from huggingface_hub import HfApi  # type: ignore[import-not-found]
    except ImportError:
        return ModelSizeEstimate(
            model_id=model_id,
            hf_repo=row.hf_repo,
            reason="huggingface_hub not installed (uv sync --extra train)",
        )
    try:
        from openpathai.config import hf as _hf

        token = _hf.resolve_token()
        info = HfApi().model_info(row.hf_repo, token=token, files_metadata=True)
    except Exception as exc:  # network / gated / etc.
        return ModelSizeEstimate(
            model_id=model_id,
            hf_repo=row.hf_repo,
            reason=f"HfApi.model_info failed: {exc}",
        )
    siblings = getattr(info, "siblings", None) or []
    sizes: list[int] = []
    for s in siblings:
        size = getattr(s, "size", None)
        if isinstance(size, int):
            sizes.append(size)
    if not sizes:
        result = ModelSizeEstimate(
            model_id=model_id,
            hf_repo=row.hf_repo,
            file_count=len(siblings),
            reason="HF API did not return per-file sizes",
        )
        _SIZE_ESTIMATE_CACHE[model_id] = result
        return result
    result = ModelSizeEstimate(
        model_id=model_id,
        hf_repo=row.hf_repo,
        size_bytes=sum(sizes),
        file_count=len(siblings),
    )
    _SIZE_ESTIMATE_CACHE[model_id] = result
    return result


def _foundation_adapter(model_id: str) -> Any | None:
    try:
        from openpathai.foundation.registry import default_foundation_registry

        return default_foundation_registry().get(model_id)
    except Exception:
        return None


def _detection_adapter(model_id: str) -> Any | None:
    try:
        from openpathai.detection.registry import default_detection_registry

        return default_detection_registry().get(model_id)
    except Exception:
        return None


@router.post(
    "/{model_id}/download",
    summary="Download a model's weights via its adapter's pretrained build",
    response_model=ModelDownloadResult,
)
async def download_model(model_id: str) -> ModelDownloadResult:
    row = _resolve_model_row(model_id)

    pre_status = _local_status_for_row(row)
    if pre_status.present:
        return ModelDownloadResult(
            model_id=model_id,
            status="already_present",
            target_dir=pre_status.target_dir,
            size_bytes=pre_status.size_bytes,
            file_count=pre_status.file_count,
            message="Weights already cached.",
        )

    adapter = _foundation_adapter(model_id) or _detection_adapter(model_id)
    if adapter is None:
        return ModelDownloadResult(
            model_id=model_id,
            status="error",
            target_dir=None,
            message=(
                "No buildable adapter is registered for this model "
                f"({model_id!r}). Classifier-zoo cards download lazily on first "
                "use via the Train route."
            ),
        )

    # Build the backbone — this triggers timm / huggingface_hub fetches.
    try:
        adapter.build(pretrained=True)
    except ImportError as exc:
        return ModelDownloadResult(
            model_id=model_id,
            status="missing_backend",
            target_dir=None,
            message=str(exc),
            install_cmd="uv sync --extra train",
        )
    except Exception as exc:
        # Phase 21.9 chunk A3 — classify gated failures by type. The
        # foundation stubs raise ``GatedAccessError`` (a ``RuntimeError``
        # subclass) on ``.build()`` regardless of their message, so the
        # legacy text-matching path missed them. Catch by type first;
        # fall back to text-matching for adapters that wrap upstream
        # 401/403 errors as plain RuntimeErrors.
        from openpathai.foundation.fallback import GatedAccessError

        is_gated = isinstance(exc, GatedAccessError)
        if not is_gated:
            msg_lower = str(exc).lower()
            is_gated = (
                "gated" in msg_lower
                or "401" in msg_lower
                or "403" in msg_lower
                or "request access" in msg_lower
            )

        if is_gated and row.hf_repo:
            message = (
                f"{row.id} is gated. Request access at "
                f"https://huggingface.co/{row.hf_repo} and configure your "
                "HF token under Settings → Hugging Face."
            )
        elif is_gated:
            message = (
                f"{row.id} is gated. Configure your HF token under "
                "Settings → Hugging Face after requesting access on the "
                "upstream page."
            )
        else:
            message = str(exc)

        return ModelDownloadResult(
            model_id=model_id,
            status="gated" if is_gated else "error",
            target_dir=None,
            message=message,
            install_cmd=None,
            resolved_id=getattr(adapter, "id", None),
        )

    post_status = _local_status_for_row(row)
    return ModelDownloadResult(
        model_id=model_id,
        status="downloaded",
        target_dir=post_status.target_dir,
        size_bytes=post_status.size_bytes,
        file_count=post_status.file_count,
        message=(
            "Weights cached."
            if post_status.present
            else "Adapter built but no on-disk cache was found."
        ),
        resolved_id=getattr(adapter, "id", model_id),
    )
