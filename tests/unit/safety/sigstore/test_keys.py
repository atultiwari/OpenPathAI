"""Keypair generation + loading round-trips."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from openpathai.safety.sigstore import (
    SigstoreError,
    default_key_path,
    generate_keypair,
    load_keypair,
)


def test_generate_writes_both_files(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    private_path, public_path = generate_keypair(priv)
    assert private_path == priv
    assert public_path == priv.with_name("ed25519.pub")
    assert priv.exists()
    assert priv.with_name("ed25519.pub").exists()
    assert priv.stat().st_size == 32
    assert public_path.stat().st_size == 32


def test_generate_refuses_overwrite(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    with pytest.raises(SigstoreError, match="already exists"):
        generate_keypair(priv)


def test_generate_force_overwrites(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    first_bytes = priv.read_bytes()
    generate_keypair(priv, force=True)
    assert priv.read_bytes() != first_bytes  # new random key


def test_load_roundtrip(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    sk, pk = load_keypair(priv)
    # The keys support the Ed25519 sign/verify protocol.
    signature = sk.sign(b"hello")
    pk.verify(signature, b"hello")


def test_load_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(SigstoreError, match="not found"):
        load_keypair(tmp_path / "nonexistent")


def test_load_malformed_raises(tmp_path: Path) -> None:
    priv = tmp_path / "bogus"
    priv.write_bytes(b"not-an-ed25519-key")
    with pytest.raises(SigstoreError, match="malformed"):
        load_keypair(priv)


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Windows doesn't honour POSIX perm bits the same way",
)
def test_private_key_chmod_0600(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    mode = stat.S_IMODE(os.stat(priv).st_mode)
    # Only the owner should read/write.
    assert mode == 0o600


def test_default_key_path_honours_openpathai_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))
    expected = tmp_path / "home" / "keys" / "ed25519"
    assert default_key_path() == expected


def test_load_uses_embedded_public_when_pub_missing(tmp_path: Path) -> None:
    priv = tmp_path / "ed25519"
    generate_keypair(priv)
    priv.with_name("ed25519.pub").unlink()
    sk, pk = load_keypair(priv)
    # Derived public key still verifies.
    pk.verify(sk.sign(b"payload"), b"payload")
