"""PHI-redaction at the JSON-serialisation boundary (Phase 19).

Iron rule #8 says filesystem paths and patient identifiers must
never be rendered in plain text outside the private audit DB. The
FastAPI app enforces this twice:

1. **Schema level** — every pydantic response model either omits
   path fields outright or routes them through
   :func:`redact_manifest_path` on population.
2. **Network level** — a response-body middleware scans the final
   JSON for obvious path-shaped strings and rewrites them. The
   middleware is defence-in-depth; the schema-level redaction is
   the primary enforcement.

This module exposes both the scalar helpers + the middleware.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from openpathai.safety.audit.phi import hash_filename, redact_manifest_path, strip_phi

__all__ = [
    "PHI_PATH_REGEX",
    "hash_filename",
    "hash_patient_id",
    "library_whitelist_prefixes",
    "redact_manifest_path",
    "redact_response_payload",
    "strip_phi",
]


_UNIX_PATH_SUBRE = r"(?:/Users/|/home/|/root/)[^\s\"']+"

# Windows drive-letter paths: ``C:\foo\bar``. The character after the
# backslash must start an identifier — this keeps JSON escape sequences
# like ``"is:\n"`` or ``"model:\tnew"`` from being flagged as paths.
_WINDOWS_PATH_SUBRE = r"[A-Za-z]:\\(?![nrtbfu0v/\\\"' ])[A-Za-z0-9_][^\s\"']*"

PHI_PATH_REGEX = re.compile(f"(?:{_UNIX_PATH_SUBRE}|{_WINDOWS_PATH_SUBRE})")
"""Matches unix /Users/... /home/... /root/... and Windows C:\\... paths
inside a JSON response body. Windows escape sequences (``\\n``, ``\\t``)
are excluded so dataset prose doesn't false-positive."""


def hash_patient_id(value: str | None) -> str:
    """Return the short ``pt-<sha256[:8]>`` form used in browser
    dataframes so the same patient collates across rows without
    the raw id ever landing in the wire payload.
    """
    if not value:
        return ""
    return "pt-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def redact_response_payload(payload: Any) -> Any:
    """Recursively redact path-shaped strings in a response
    payload. Used as the last line of defence before JSON
    serialisation.

    - ``str`` values matching :data:`PHI_PATH_REGEX` are rewritten
      via :func:`redact_manifest_path`.
    - ``dict``/``list`` values recurse.
    - Every other scalar passes through unchanged.
    """
    if isinstance(payload, Mapping):
        return {str(k): redact_response_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [redact_response_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return [redact_response_payload(item) for item in payload]
    if isinstance(payload, str):
        return _redact_string(payload)
    return payload


def _redact_match(path_str: str) -> str:
    """Windows-aware ``basename#hash`` rewrite.

    :func:`openpathai.safety.audit.phi.redact_manifest_path` uses
    :class:`pathlib.Path`, which on POSIX does not split on ``\\``. A
    Windows-style path arriving in the middleware would therefore
    round-trip unchanged. We handle both separators manually.
    """
    cut = max(path_str.rfind("/"), path_str.rfind("\\"))
    if cut < 0:
        return path_str
    basename = path_str[cut + 1 :]
    parent = path_str[:cut]
    parent_hash = hashlib.sha256(parent.encode("utf-8")).hexdigest()[:8]
    return f"{basename}#{parent_hash}"


def library_whitelist_prefixes() -> tuple[str, ...]:
    """Phase 21.7 chunk B — paths the canvas legitimately needs to read.

    These directories contain library-managed cache / config / artifact
    bytes that are never PHI. Surfacing them unredacted lets the user
    actually copy a path from the wizard or Settings into a shell.

    The list is computed per-call so test fixtures that monkeypatch
    ``OPENPATHAI_HOME`` / ``HF_HOME`` see the change immediately.
    """
    home = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai")).resolve()
    hf_home_env = os.environ.get("HF_HOME")
    hf_root = Path(hf_home_env).resolve() if hf_home_env else Path.home() / ".cache" / "huggingface"
    xdg_env = os.environ.get("XDG_CACHE_HOME")
    xdg_hf = Path(xdg_env).resolve() / "huggingface" if xdg_env else None
    prefixes = [str(home), str(hf_root)]
    if xdg_hf is not None:
        prefixes.append(str(xdg_hf))
    return tuple(prefixes)


def _redact_string(value: str) -> str:
    # Short-circuit when nothing matches — the common case.
    if not PHI_PATH_REGEX.search(value):
        return value
    whitelist = library_whitelist_prefixes()
    return PHI_PATH_REGEX.sub(
        lambda m: (
            m.group(0)
            if any(m.group(0).startswith(prefix) for prefix in whitelist)
            else _redact_match(m.group(0))
        ),
        value,
    )
