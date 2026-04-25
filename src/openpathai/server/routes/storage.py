"""Storage paths surface (Phase 21.6 chunk C).

The canvas needs a single source of truth for *where* every artifact
type is written. Hard-coding `~/.openpathai/...` strings in the React
shell drifts the moment a user sets `OPENPATHAI_HOME` or
`HF_HOME` — this endpoint resolves them all in one round-trip.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from openpathai.config import hf as hf_config
from openpathai.data.downloaders import default_download_root
from openpathai.server.auth import AuthDependency

__all__ = ["StoragePaths", "router"]


router = APIRouter(
    prefix="/storage",
    tags=["storage"],
    dependencies=[AuthDependency],
)


class StoragePaths(BaseModel):
    """Resolved on-disk locations for every artifact category.

    Every value is an absolute path. Some paths may not exist yet —
    callers that care should `mkdir -p` themselves (the GUI
    surfaces "Open in Finder" rather than creating directories on a
    user's behalf).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    openpathai_home: str
    datasets: str
    models: str
    checkpoints: str
    dzi: str
    audit_db: str
    cache: str
    secrets: str
    hf_hub_cache: str
    pipelines: str


def _home() -> Path:
    return Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))


def _hf_hub_cache() -> Path:
    """Mirror huggingface_hub's resolution without importing it.

    Order: ``HF_HOME`` → ``$XDG_CACHE_HOME/huggingface`` → ``~/.cache/huggingface``.
    """
    if hf_home := os.environ.get("HF_HOME"):
        return Path(hf_home) / "hub"
    if xdg := os.environ.get("XDG_CACHE_HOME"):
        return Path(xdg) / "huggingface" / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


@router.get(
    "/paths",
    summary="Resolved on-disk locations for every artifact category",
    response_model=StoragePaths,
)
async def get_storage_paths() -> StoragePaths:
    home = _home()
    return StoragePaths(
        openpathai_home=str(home),
        datasets=str(default_download_root()),
        models=str(home / "models"),
        checkpoints=str(home / "checkpoints"),
        dzi=str(home / "dzi"),
        audit_db=str(home / "audit.sqlite"),
        cache=str(home / "cache"),
        secrets=str(hf_config.secrets_path()),
        hf_hub_cache=str(_hf_hub_cache()),
        pipelines=str(home / "pipelines"),
    )
