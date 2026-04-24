"""Phase-17 sigstore endpoints (Phase 19)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency

__all__ = ["router"]


router = APIRouter(
    prefix="/manifest",
    tags=["manifest"],
    dependencies=[AuthDependency],
)


class SignRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest: dict[str, Any]
    key_path: str | None = Field(default=None, description="Override private key path")


class VerifyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest: dict[str, Any]
    signature: dict[str, Any]


@router.post("/sign", summary="Sign a manifest payload")
async def sign_manifest(body: SignRequest) -> dict[str, Any]:
    from openpathai.safety.sigstore import default_key_path
    from openpathai.safety.sigstore import sign_manifest as _sign
    from openpathai.safety.sigstore.schema import SigstoreError

    key_path = Path(body.key_path).expanduser() if body.key_path else default_key_path()
    if not key_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"private key not found at {key_path}. Run `openpathai manifest keygen` first."
            ),
        )
    try:
        signature = _sign(body.manifest, key_path=key_path)
    except SigstoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return signature.model_dump(mode="json")


@router.post("/verify", summary="Verify a signed manifest")
async def verify_manifest(body: VerifyRequest) -> dict[str, Any]:
    from openpathai.safety.sigstore import ManifestSignature
    from openpathai.safety.sigstore import verify_manifest as _verify
    from openpathai.safety.sigstore.schema import SigstoreError

    try:
        sig = ManifestSignature.model_validate(body.signature)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid signature payload: {exc!s}",
        ) from exc
    try:
        outcome = _verify(body.manifest, signature=sig)
    except SigstoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return {
        "valid": bool(outcome),
        "public_key_b64": sig.public_key_b64,
        "algorithm": sig.algorithm,
    }
