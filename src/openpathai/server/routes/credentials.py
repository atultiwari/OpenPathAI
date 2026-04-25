"""Credentials API (Phase 21.5 chunk C).

Currently exposes one secret — the Hugging Face token — but lives in
its own router so the canvas Settings card can grow into a generic
"credentials" surface (HF, sigstore identity, MLflow, …) without
polluting other routers.

Wire shapes are intentionally redacted: the GET / PUT / TEST handlers
only ever return the source + the last four characters of the token,
never the token itself. The actual write goes through
:func:`openpathai.config.hf.set_token`, which sets file mode 0600.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.config import hf as hf_config
from openpathai.server.auth import AuthDependency

__all__ = ["router"]


router = APIRouter(
    prefix="/credentials",
    tags=["credentials"],
    dependencies=[AuthDependency],
)


class HFTokenStatusOut(BaseModel):
    """Public-safe HF token status."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    present: bool
    source: str
    token_preview: str | None = None


class HFTokenSetIn(BaseModel):
    """Body for ``PUT /credentials/huggingface``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    token: str = Field(min_length=1)


class HFTokenSetOut(BaseModel):
    """Response after a successful PUT."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    saved: bool
    secrets_path: str
    status: HFTokenStatusOut


class HFTokenClearOut(BaseModel):
    """Response after DELETE."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cleared: bool
    status: HFTokenStatusOut


class HFTokenTestOut(BaseModel):
    """Response from POST .../test — calls huggingface_hub.whoami when
    available, otherwise reports a structured ``unavailable`` reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    user: str | None = None
    reason: str | None = None
    status: HFTokenStatusOut


def _status_out() -> HFTokenStatusOut:
    s = hf_config.status()
    return HFTokenStatusOut(
        present=s.present,
        source=s.source,
        token_preview=s.token_preview,
    )


@router.get(
    "/huggingface",
    summary="Get the redacted Hugging Face token status",
    response_model=HFTokenStatusOut,
)
async def get_hf_status() -> HFTokenStatusOut:
    return _status_out()


@router.put(
    "/huggingface",
    summary="Persist a Hugging Face token to ~/.openpathai/secrets.json",
    response_model=HFTokenSetOut,
)
async def put_hf_token(body: HFTokenSetIn) -> HFTokenSetOut:
    try:
        path = hf_config.set_token(body.token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return HFTokenSetOut(
        saved=True,
        secrets_path=str(path),
        status=_status_out(),
    )


@router.delete(
    "/huggingface",
    summary="Remove the Hugging Face token from the settings file",
    response_model=HFTokenClearOut,
)
async def delete_hf_token() -> HFTokenClearOut:
    cleared = hf_config.clear_token()
    return HFTokenClearOut(cleared=cleared, status=_status_out())


@router.post(
    "/huggingface/test",
    summary="Probe huggingface_hub.whoami() with the resolved token",
    response_model=HFTokenTestOut,
)
async def test_hf_token() -> HFTokenTestOut:
    snapshot = _status_out()
    token = hf_config.resolve_token()
    if token is None:
        return HFTokenTestOut(
            ok=False,
            reason="no_token_configured",
            status=snapshot,
        )

    try:
        from huggingface_hub import whoami  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - missing extra
        return HFTokenTestOut(
            ok=False,
            reason=f"huggingface_hub_unavailable: {exc!s}",
            status=snapshot,
        )

    try:
        info: Any = whoami(token=token)
    except Exception as exc:  # pragma: no cover - network / auth failures
        return HFTokenTestOut(
            ok=False,
            reason=f"whoami_failed: {exc!s}",
            status=snapshot,
        )

    user_name: str | None = None
    if isinstance(info, dict):
        candidate = info.get("name") or info.get("user") or info.get("username")
        if isinstance(candidate, str):
            user_name = candidate
    return HFTokenTestOut(ok=True, user=user_name, status=snapshot)
