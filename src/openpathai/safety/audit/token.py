"""Delete-token store for :meth:`AuditDB.delete_before`.

Master-plan §17 "Auth on audit" says destructive pruning must require
a token, **not** a hardcoded PIN. Phase 8 ships the v0.2 half of that
promise: a UUIDv4 stored via ``keyring`` on platforms that support it,
with a chmod-0600 file fallback under ``$OPENPATHAI_HOME/audit.token``
for headless Linux CI and Docker images where no D-Bus session is
available.

Phase 17 (Diagnostic mode) will extend the story with network-exposed
auth; Phase 8 keeps it strictly local.
"""

from __future__ import annotations

import contextlib
import hmac
import os
import secrets
from pathlib import Path
from typing import Literal

__all__ = [
    "KEYRING_KEY",
    "KEYRING_SERVICE",
    "KeyringTokenStore",
    "TokenStoreBackend",
]


KEYRING_SERVICE: str = "openpathai"
KEYRING_KEY: str = "audit-delete-token"


TokenStoreBackend = Literal["keyring", "file", "unset"]


def _token_fallback_path() -> Path:
    """Location of the file-backed fallback token."""
    root = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))
    return root / "audit.token"


class KeyringTokenStore:
    """Stores the audit delete token via :mod:`keyring` (preferred) or a
    chmod-0600 file fallback.

    Parameters
    ----------
    service:
        Keyring "service" slot. Defaults to :data:`KEYRING_SERVICE`.
    key:
        Keyring "username" slot. Defaults to :data:`KEYRING_KEY`.
    allow_file_fallback:
        Whether to drop to a ``$OPENPATHAI_HOME/audit.token`` file when
        the keyring backend is unavailable. Defaults to ``True``.
    """

    def __init__(
        self,
        *,
        service: str = KEYRING_SERVICE,
        key: str = KEYRING_KEY,
        allow_file_fallback: bool = True,
    ) -> None:
        self._service = service
        self._key = key
        self._allow_file = allow_file_fallback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init(self) -> tuple[str, TokenStoreBackend]:
        """Generate + store a fresh token. Return ``(token, backend)``.

        Callers print the token **once** and never again — the store
        supports verification (not retrieval) from then on.
        """
        token = secrets.token_hex(16)
        backend = self._set(token)
        return token, backend

    def verify(self, candidate: str) -> bool:
        """Constant-time compare ``candidate`` against the stored token.

        Returns ``False`` when no token has been set.
        """
        stored = self._get()
        if stored is None or not candidate:
            return False
        return hmac.compare_digest(stored.encode("utf-8"), candidate.encode("utf-8"))

    def status(self) -> dict[str, str]:
        """Return ``{"store": "keyring"|"file"|"unset", "set": bool}``.

        Introspection-only — never exposes the token itself.
        """
        # Probe keyring first.
        try:
            import keyring

            existing = keyring.get_password(self._service, self._key)
            if existing is not None:
                return {"store": "keyring", "set": "true"}
        except Exception:
            pass
        # Fall through to file backend.
        path = _token_fallback_path()
        if path.is_file() and self._allow_file:
            return {"store": "file", "set": "true"}
        return {"store": "unset", "set": "false"}

    def clear(self) -> None:
        """Forget the current token. Used by tests and re-init flows."""
        try:
            import keyring

            keyring.delete_password(self._service, self._key)
        except Exception:
            pass
        path = _token_fallback_path()
        if path.exists():
            path.unlink()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _set(self, token: str) -> TokenStoreBackend:
        """Attempt keyring, fall back to file on any failure."""
        try:
            import keyring

            keyring.set_password(self._service, self._key, token)
            return "keyring"
        except Exception:
            if not self._allow_file:
                raise
        return self._set_file(token)

    def _set_file(self, token: str) -> TokenStoreBackend:
        path = _token_fallback_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")
        # Windows chmod is advisory; still honour the write if it fails.
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)
        return "file"

    def _get(self) -> str | None:
        # Prefer keyring when available.
        try:
            import keyring

            value = keyring.get_password(self._service, self._key)
            if value is not None:
                return value
        except Exception:
            pass
        if not self._allow_file:
            return None
        path = _token_fallback_path()
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
        return None
