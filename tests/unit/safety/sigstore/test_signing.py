"""Sign / verify round-trips + tampered-manifest detection."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from openpathai.safety.sigstore import (
    ManifestSignature,
    SigstoreError,
    generate_keypair,
    sign_manifest,
    verify_manifest,
)


def _manifest(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "run_id": "run-abc",
        "pipeline_id": "demo",
        "mode": "diagnostic",
        "graph_hash": "deadbeef",
        "datasets": ["lc25000"],
        "models": ["resnet18"],
    }
    base.update(overrides)
    return base


def test_sign_verify_roundtrip(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    manifest = _manifest()
    sig = sign_manifest(manifest, key_path=priv, generate_if_missing=False)
    assert isinstance(sig, ManifestSignature)
    assert verify_manifest(manifest, sig) is True


def test_sign_autogenerates_missing_key(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    # No prior generate_keypair; sign should create one.
    sig = sign_manifest(_manifest(), key_path=priv)
    assert priv.exists()
    assert priv.with_name("ed25519.pub").exists()
    assert isinstance(sig, ManifestSignature)


def test_tampered_manifest_fails_verify(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    manifest = _manifest()
    sig = sign_manifest(manifest, key_path=priv, generate_if_missing=False)
    tampered = dict(manifest)
    tampered["datasets"] = ["different-data"]
    assert verify_manifest(tampered, sig) is False


def test_tampered_signature_fails_verify(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    manifest = _manifest()
    sig = sign_manifest(manifest, key_path=priv, generate_if_missing=False)
    # Flip one byte of the signature.
    raw_sig = bytearray(base64.b64decode(sig.signature_b64))
    raw_sig[0] ^= 0xFF
    tampered = ManifestSignature(
        manifest_hash=sig.manifest_hash,
        signature_b64=base64.b64encode(bytes(raw_sig)).decode("ascii"),
        public_key_b64=sig.public_key_b64,
        algorithm=sig.algorithm,
        signed_at=sig.signed_at,
    )
    assert verify_manifest(manifest, tampered) is False


def test_wrong_public_key_fails_verify(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    manifest = _manifest()
    sig = sign_manifest(manifest, key_path=priv, generate_if_missing=False)
    # Swap in a fresh public key.
    other_priv = tmp_path / "other"
    _, other_pub = generate_keypair(other_priv)
    other_pub_b64 = base64.b64encode(other_pub.read_bytes()).decode("ascii")
    mismatched = ManifestSignature(
        manifest_hash=sig.manifest_hash,
        signature_b64=sig.signature_b64,
        public_key_b64=other_pub_b64,
        algorithm=sig.algorithm,
        signed_at=sig.signed_at,
    )
    assert verify_manifest(manifest, mismatched) is False


def test_unsupported_algorithm_raises(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    manifest = _manifest()
    sig = sign_manifest(manifest, key_path=priv, generate_if_missing=False)
    # Directly construct one with an unsupported algorithm; pydantic's
    # Literal type rejects it at validation time.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ManifestSignature(
            manifest_hash=sig.manifest_hash,
            signature_b64=sig.signature_b64,
            public_key_b64=sig.public_key_b64,
            algorithm="rsa-4096",  # type: ignore[arg-type]
            signed_at=sig.signed_at,
        )
    assert sig.algorithm == "ed25519"


def test_malformed_signature_payload_raises(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    manifest = _manifest()
    sig = sign_manifest(manifest, key_path=priv, generate_if_missing=False)
    broken = ManifestSignature(
        manifest_hash=sig.manifest_hash,
        signature_b64="not-base64!!",
        public_key_b64=sig.public_key_b64,
        algorithm=sig.algorithm,
        signed_at=sig.signed_at,
    )
    with pytest.raises(SigstoreError, match="malformed base64"):
        verify_manifest(manifest, broken)
