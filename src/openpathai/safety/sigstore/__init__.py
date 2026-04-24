"""OpenPathAI — local-keypair manifest signing (Phase 17).

Phase 17's Bet 3 closure ships Ed25519 signatures on every
``RunManifest`` produced in diagnostic mode. The format is
byte-compatible with a future cosign / Rekor upgrade (the
``ManifestSignature`` schema only references standard
algorithm + base64 fields); no network round-trip is required
today.

Public surface:

* :class:`ManifestSignature` — frozen pydantic record of the
  signature + embedded public key.
* :class:`SigstoreError` — raised by sign / verify on key or
  signature failures.
* :func:`generate_keypair` + :func:`load_keypair` — filesystem-
  backed key management under ``$OPENPATHAI_HOME/keys/``.
* :func:`sign_manifest` + :func:`verify_manifest` — the actual
  sign / verify round trip over a canonical JSON dump.
* :func:`default_key_path` — the conventional keypath honouring
  ``OPENPATHAI_HOME``.
"""

from __future__ import annotations

from openpathai.safety.sigstore.keys import (
    default_key_path,
    generate_keypair,
    load_keypair,
)
from openpathai.safety.sigstore.schema import (
    ManifestSignature,
    SigstoreError,
)
from openpathai.safety.sigstore.signing import (
    sign_manifest,
    verify_manifest,
)

__all__ = [
    "ManifestSignature",
    "SigstoreError",
    "default_key_path",
    "generate_keypair",
    "load_keypair",
    "sign_manifest",
    "verify_manifest",
]
