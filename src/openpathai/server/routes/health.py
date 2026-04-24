"""Public health + version endpoints (Phase 19).

Only router whose endpoints are reachable without a bearer token —
load-balancer liveness probes must not need credentials.
"""

from __future__ import annotations

import importlib.metadata as _metadata
import os
import subprocess

from fastapi import APIRouter, Request

from openpathai.server.schemas import HealthResponse, VersionResponse

__all__ = ["router"]

router = APIRouter(tags=["health"])


def _installed_version() -> str:
    try:
        return _metadata.version("openpathai")
    except _metadata.PackageNotFoundError:  # pragma: no cover - editable install corner case
        return "0.0.0+unknown"


def _commit_sha() -> str | None:
    env_sha = os.environ.get("OPENPATHAI_COMMIT_SHA")
    if env_sha:
        return env_sha
    try:  # pragma: no cover - git availability depends on the deploy target
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns 200 without requiring authentication.",
    response_model=HealthResponse,
)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(api_version=request.app.state.settings.api_version)


@router.get(
    "/version",
    summary="Installed library + API version",
    response_model=VersionResponse,
)
async def version(request: Request) -> VersionResponse:
    return VersionResponse(
        openpathai_version=_installed_version(),
        api_version=request.app.state.settings.api_version,
        commit=_commit_sha(),
    )
