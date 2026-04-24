"""Node catalog (Phase 19).

The React canvas (Phase 20) paints one draggable node per entry
returned here. Each node carries its input + output JSON schemas
(derived from the pydantic Input / Output models registered by
``@openpathai.node``), so the canvas can auto-generate forms
without re-declaring types client-side.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.pipeline.node import REGISTRY as NODE_REGISTRY
from openpathai.server.auth import AuthDependency

__all__ = ["NodeSummary", "router"]


router = APIRouter(
    prefix="/nodes",
    tags=["nodes"],
    dependencies=[AuthDependency],
)


class NodeSummary(BaseModel):
    """Wire shape for one registered ``@openpathai.node``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    description: str = ""
    code_hash: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


def _summarise(node_id: str) -> NodeSummary:
    definition = NODE_REGISTRY.get(node_id)
    doc = (definition.fn.__doc__ or "").strip()
    first_line = doc.splitlines()[0] if doc else ""
    return NodeSummary(
        id=node_id,
        description=definition.tooltip or first_line,
        code_hash=definition.code_hash,
        input_schema=definition.input_type.model_json_schema(),
        output_schema=definition.output_type.model_json_schema(),
    )


@router.get("", summary="List registered pipeline nodes")
async def list_nodes() -> dict[str, Any]:
    ids = sorted(NODE_REGISTRY.all().keys())
    items = [_summarise(nid) for nid in ids]
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": len(items),
    }


@router.get(
    "/{node_id}",
    summary="Retrieve one node definition",
    response_model=NodeSummary,
)
async def get_node(node_id: str) -> NodeSummary:
    try:
        return _summarise(node_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown node {node_id!r}",
        ) from exc
