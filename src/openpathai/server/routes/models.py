"""Unified model registry view (Phase 19).

Merges the classification zoo (``models/zoo/*.yaml``), the
foundation backbones (Phase 13), the detection adapters (Phase 14),
and the segmentation adapters (Phase 14) into a single flat list.
Each row carries a ``kind`` field so the React canvas can group
them in the palette.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency

__all__ = ["ModelSummary", "router"]


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
