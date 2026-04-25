"""Hugging Face token resolution (Phase 21.5 chunk C).

A single source of truth for *which* HF token the rest of the library
should use. Resolution order, highest precedence first:

1. ``$OPENPATHAI_HOME/secrets.json`` — written from the canvas's
   Settings → Hugging Face card or with :func:`set_token`.
2. ``HF_TOKEN`` env var (transformers convention).
3. ``HUGGING_FACE_HUB_TOKEN`` env var (huggingface-hub CLI convention).

When nothing is configured, callers see ``resolve_token() -> None`` and
the existing fallback machinery in :mod:`openpathai.foundation.fallback`
takes over (DINOv2 substitute + audit-recorded ``fallback_reason``).

The secrets file is written with mode ``0600``; tokens never appear in
log lines. Public API surfaces only ever return a redacted preview
("…last4") via :class:`HFTokenStatus`.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

__all__ = [
    "ENV_HF_HUB_TOKEN",
    "ENV_HF_TOKEN",
    "SECRETS_FILENAME",
    "HFTokenSource",
    "HFTokenStatus",
    "clear_token",
    "is_token_present",
    "resolve_token",
    "secrets_path",
    "set_token",
    "status",
]

ENV_HF_TOKEN = "HF_TOKEN"
ENV_HF_HUB_TOKEN = "HUGGING_FACE_HUB_TOKEN"
SECRETS_FILENAME = "secrets.json"

HFTokenSource = Literal["settings", "env_hf_token", "env_hub_token", "none"]


@dataclass(frozen=True)
class HFTokenStatus:
    """Public-safe view of the HF token state.

    ``token_preview`` is at most the last four characters of the
    resolved token, prefixed with ``…``. ``None`` when no token is
    configured.
    """

    present: bool
    source: HFTokenSource
    token_preview: str | None


def _home() -> Path:
    """Mirror ``openpathai.server.config._default_home`` without the
    server-side import (avoids a cycle)."""
    return Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))


def secrets_path() -> Path:
    """Absolute path to the on-disk secrets file. Not necessarily existing."""
    return _home() / SECRETS_FILENAME


def _read_secrets() -> dict[str, str]:
    path = secrets_path()
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def _write_secrets(payload: dict[str, str]) -> Path:
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    tmp.replace(path)
    # Some filesystems (notably FAT/exFAT on USB) don't honour POSIX
    # modes. The token file is still scoped to the user's home; chmod
    # is defence-in-depth, not a hard guarantee.
    with contextlib.suppress(OSError):
        path.chmod(0o600)
    return path


def _preview(token: str) -> str:
    if len(token) <= 4:
        return "…" + token
    return "…" + token[-4:]


def resolve_token() -> str | None:
    """Return the HF token to use, or ``None`` when none is configured.

    Settings file wins over env vars so a freshly-installed user can
    paste their token into the Settings card without editing shells.
    """
    secrets = _read_secrets()
    candidate = secrets.get("hf_token")
    if candidate:
        return candidate
    env_hf = os.environ.get(ENV_HF_TOKEN)
    if env_hf:
        return env_hf
    env_hub = os.environ.get(ENV_HF_HUB_TOKEN)
    if env_hub:
        return env_hub
    return None


def is_token_present() -> bool:
    """Cheaper presence check — does not return the token itself."""
    return resolve_token() is not None


def status() -> HFTokenStatus:
    """Redacted status suitable for logging or returning over the API."""
    secrets = _read_secrets()
    candidate = secrets.get("hf_token")
    if candidate:
        return HFTokenStatus(present=True, source="settings", token_preview=_preview(candidate))
    env_hf = os.environ.get(ENV_HF_TOKEN)
    if env_hf:
        return HFTokenStatus(present=True, source="env_hf_token", token_preview=_preview(env_hf))
    env_hub = os.environ.get(ENV_HF_HUB_TOKEN)
    if env_hub:
        return HFTokenStatus(present=True, source="env_hub_token", token_preview=_preview(env_hub))
    return HFTokenStatus(present=False, source="none", token_preview=None)


def set_token(token: str) -> Path:
    """Persist ``token`` to the secrets file. Returns the file path.

    Raises :class:`ValueError` for empty / whitespace-only tokens.
    """
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("HF token must not be empty.")
    secrets = _read_secrets()
    secrets["hf_token"] = cleaned
    return _write_secrets(secrets)


def clear_token() -> bool:
    """Remove the HF token from the secrets file. Returns ``True`` if a
    token was actually deleted, ``False`` if there was nothing to clear."""
    secrets = _read_secrets()
    if "hf_token" not in secrets:
        return False
    del secrets["hf_token"]
    if secrets:
        _write_secrets(secrets)
    else:
        # File is now empty — remove it entirely so the caller sees a
        # clean "nothing configured" state.
        with contextlib.suppress(FileNotFoundError):
            secrets_path().unlink()
    return True
