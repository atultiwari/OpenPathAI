"""Optional-extras status (Phase 21.7 chunk D).

The wizard surfaces ``missing_backend`` envelopes from the dataset
download + train routes when an optional extra isn't installed. This
endpoint lets the UI render a copy-able install command instead of
the raw ImportError text.

Each extra is identified by:

* a probe import — when the import succeeds, ``installed=True``.
* the documented ``install_cmd`` users should run from the repo root.

Adding a new extra here is a one-line append to :data:`_EXTRAS`.
"""

from __future__ import annotations

import importlib
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from openpathai.server.auth import AuthDependency

__all__ = ["ExtraStatus", "router"]


router = APIRouter(prefix="/extras", tags=["extras"], dependencies=[AuthDependency])


_EXTRAS: tuple[tuple[str, str, str, str], ...] = (
    # (name, probe-import, install-cmd, one-line description)
    ("server", "fastapi", "uv sync --extra server", "FastAPI + uvicorn for /v1 routes."),
    ("data", "PIL", "uv sync --extra data", "scikit-image + tifffile + Pillow for tile I/O."),
    (
        "train",
        "torch",
        "uv sync --extra train",
        "torch + Lightning + timm for real training runs.",
    ),
    (
        "wsi",
        "openslide",
        "uv sync --extra wsi",
        "openslide-python + tiatoolbox for whole-slide image I/O.",
    ),
    (
        "explain",
        "huggingface_hub",
        "uv sync --extra explain",
        "Grad-CAM, IG, attention rollout (transitively pulls huggingface_hub).",
    ),
    (
        "safety",
        "reportlab",
        "uv sync --extra safety",
        "ReportLab for PDF QC reports + clinical-grade banners.",
    ),
    (
        "kaggle",
        "kaggle",
        "uv sync --extra kaggle",
        "Kaggle CLI for kaggle-method dataset downloads.",
    ),
    (
        "gui",
        "gradio",
        "uv sync --extra gui",
        "Gradio 5 for the legacy doctor-shaped GUI.",
    ),
    (
        "mlflow",
        "mlflow",
        "uv sync --extra mlflow",
        "MLflow tracking sink for Phase 10+ run history.",
    ),
)


class ExtraStatus(BaseModel):
    """Wire shape for one optional extra."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    installed: bool
    install_cmd: str
    description: str


def _probe(module: str) -> bool:
    """Try to import ``module``; return ``True`` on success."""
    try:
        importlib.import_module(module)
    except Exception:
        return False
    return True


@router.get(
    "",
    summary="Report which optional extras are installed in the running server",
)
async def list_extras() -> dict[str, Any]:
    items = [
        ExtraStatus(
            name=name,
            installed=_probe(probe),
            install_cmd=cmd,
            description=desc,
        ).model_dump(mode="json")
        for (name, probe, cmd, desc) in _EXTRAS
    ]
    return {
        "items": items,
        "total": len(items),
    }
