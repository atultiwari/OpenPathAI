"""Sign + verify a :class:`RunManifest` with Ed25519."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpathai.safety.sigstore.keys import (
    default_key_path,
    generate_keypair,
    load_keypair,
)
from openpathai.safety.sigstore.schema import (
    ManifestSignature,
    SigstoreError,
)

__all__ = [
    "canonical_manifest_bytes",
    "sign_manifest",
    "verify_manifest",
]


def canonical_manifest_bytes(manifest: Any) -> bytes:
    """Canonical JSON bytes for a manifest (pydantic v2 model **or**
    plain dict). The bytes are the hash target; the caller never
    needs to know which path was used.
    """
    if hasattr(manifest, "model_dump"):
        payload = manifest.model_dump(mode="json")
    elif isinstance(manifest, dict):
        payload = manifest
    else:
        raise SigstoreError(
            f"manifest must be a pydantic model or dict; got {type(manifest).__name__}"
        )
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sign_manifest(
    manifest: Any,
    *,
    key_path: str | Path | None = None,
    generate_if_missing: bool = True,
) -> ManifestSignature:
    """Sign ``manifest`` with the Ed25519 keypair at ``key_path``.

    Generates a fresh keypair when the file is absent and
    ``generate_if_missing=True`` — the default so first-time
    users aren't blocked by the absent key.
    """
    path = Path(key_path).expanduser() if key_path else default_key_path()
    if not path.exists() and generate_if_missing:
        generate_keypair(path)
    try:
        sk, pk = load_keypair(path)
    except SigstoreError:
        raise

    blob = canonical_manifest_bytes(manifest)
    manifest_hash = hashlib.sha256(blob).hexdigest()
    signature = sk.sign(blob)
    public_bytes = pk.public_bytes_raw() if hasattr(pk, "public_bytes_raw") else None
    if public_bytes is None:
        # Older cryptography versions — use the raw-bytes format explicitly.
        from cryptography.hazmat.primitives import serialization

        public_bytes = pk.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    return ManifestSignature(
        manifest_hash=manifest_hash,
        signature_b64=base64.b64encode(signature).decode("ascii"),
        public_key_b64=base64.b64encode(public_bytes).decode("ascii"),
        algorithm="ed25519",
        signed_at=_utcnow_iso(),
    )


def verify_manifest(
    manifest: Any,
    signature: ManifestSignature,
) -> bool:
    """Return ``True`` when ``signature`` is a valid Ed25519 signature
    over the canonical JSON bytes of ``manifest``.

    Uses the public key embedded in ``signature`` (not a disk
    lookup), so the check is self-contained — a manifest +
    signature pair can be verified on a machine that has never
    seen the signing keypair.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if signature.algorithm != "ed25519":
        raise SigstoreError(f"unsupported signature algorithm {signature.algorithm!r}")
    try:
        public_bytes = base64.b64decode(signature.public_key_b64, validate=True)
        signature_bytes = base64.b64decode(signature.signature_b64, validate=True)
    except Exception as exc:
        raise SigstoreError(f"malformed base64 in signature payload: {exc!s}") from exc

    try:
        pk = Ed25519PublicKey.from_public_bytes(public_bytes)
    except Exception as exc:
        raise SigstoreError(f"malformed public key: {exc!s}") from exc

    blob = canonical_manifest_bytes(manifest)
    expected_hash = hashlib.sha256(blob).hexdigest()
    if expected_hash != signature.manifest_hash:
        return False
    try:
        pk.verify(signature_bytes, blob)
    except InvalidSignature:
        return False
    return True
