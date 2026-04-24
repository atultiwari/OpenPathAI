"""Signature schema + error type."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ManifestSignature",
    "SigstoreError",
]


class SigstoreError(RuntimeError):
    """Raised by sign / verify on any key- or signature-related failure."""


class ManifestSignature(BaseModel):
    """Frozen record of one manifest signature.

    Byte-compatible with a future cosign / Rekor upgrade — the
    ``algorithm`` field keys the verification routine, and the
    embedded ``public_key_b64`` makes the signature
    self-contained (no ``OPENPATHAI_HOME`` lookup required to
    verify).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_hash: str = Field(min_length=1)
    signature_b64: str = Field(min_length=1)
    public_key_b64: str = Field(min_length=1)
    algorithm: Literal["ed25519"] = "ed25519"
    signed_at: str = Field(min_length=1)
