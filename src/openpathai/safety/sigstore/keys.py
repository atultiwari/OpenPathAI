"""Ed25519 keypair generation + loading.

Filesystem convention (under ``$OPENPATHAI_HOME/keys/``):

    ed25519       — raw 32-byte private key (chmod 0600 on POSIX)
    ed25519.pub   — raw 32-byte public key

The raw-bytes format is intentional: it's byte-compatible with
OpenSSH / age-plugin-raw / any Ed25519 consumer, so a future
phase that migrates to cosign / sigstore can re-use the same
key material.

On Windows, chmod isn't honoured; we set ``stat.S_IREAD |
S_IWRITE`` which flips the read-only bit for the owning user and
document the platform tradeoff in ``docs/diagnostic-mode.md``.
"""

from __future__ import annotations

import logging
import os
import stat
import sys
from pathlib import Path
from typing import Any

from openpathai.safety.sigstore.schema import SigstoreError

_log = logging.getLogger(__name__)

__all__ = [
    "default_key_path",
    "generate_keypair",
    "load_keypair",
]


def default_key_path() -> Path:
    """Return ``$OPENPATHAI_HOME/keys/ed25519`` — the conventional
    path for the shipped sign / verify CLIs."""
    root = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))
    return root / "keys" / "ed25519"


def generate_keypair(path: str | Path | None = None, *, force: bool = False) -> tuple[Path, Path]:
    """Create a fresh Ed25519 keypair on disk.

    Returns ``(private_path, public_path)``. When ``path`` names
    an existing private key, :class:`SigstoreError` is raised
    unless ``force=True``.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_path = Path(path).expanduser() if path else default_key_path()
    public_path = private_path.with_suffix(private_path.suffix + ".pub")
    if private_path.suffix == "":
        public_path = private_path.with_name(private_path.name + ".pub")
    if private_path.exists() and not force:
        raise SigstoreError(f"key already exists at {private_path}; pass force=True to overwrite")
    private_path.parent.mkdir(parents=True, exist_ok=True)

    sk = Ed25519PrivateKey.generate()
    private_bytes = sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = sk.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    private_path.write_bytes(private_bytes)
    public_path.write_bytes(public_bytes)
    _harden_private_file(private_path)
    return private_path, public_path


def load_keypair(path: str | Path | None = None) -> tuple[Any, Any]:
    """Load the Ed25519 keypair at ``path``.

    Returns ``(private_key, public_key)`` as ``cryptography`` objects.
    Raises :class:`SigstoreError` when the file is missing or malformed.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    private_path = Path(path).expanduser() if path else default_key_path()
    public_path = private_path.with_name(private_path.name + ".pub")
    if not private_path.exists():
        raise SigstoreError(f"private key not found at {private_path}")
    raw_private = private_path.read_bytes()
    try:
        sk = Ed25519PrivateKey.from_private_bytes(raw_private)
    except Exception as exc:
        raise SigstoreError(f"malformed private key at {private_path}: {exc!s}") from exc

    if public_path.exists():
        raw_public = public_path.read_bytes()
        try:
            pk = Ed25519PublicKey.from_public_bytes(raw_public)
        except Exception as exc:
            raise SigstoreError(f"malformed public key at {public_path}: {exc!s}") from exc
    else:
        # Regenerate the public component from the private key.
        pk = sk.public_key()
    return sk, pk


def _harden_private_file(path: Path) -> None:
    """Restrict private-key read access to the owning user.

    Failure is logged (never silent) so an operator inspecting the log
    can see that the key may be world-readable — important on multi-user
    POSIX hosts where a permissions regression is a security issue.
    """
    try:
        if sys.platform.startswith("win"):  # pragma: no cover - platform-gated
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        else:
            os.chmod(path, 0o600)
    except OSError as exc:  # pragma: no cover - best-effort, logged
        _log.warning(
            "Could not harden permissions on Ed25519 private key %s: %s. "
            "On multi-user POSIX hosts, verify the file is not world-readable.",
            path,
            exc,
        )
