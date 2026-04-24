"""PHI-redaction helpers for the audit layer.

Iron rule #8 in ``CLAUDE.md`` (no PHI in plaintext) plus master-plan
§17 row "PHI handling" together require that **no filename, file path,
or DICOM patient metadata** ever hits ``audit.db``. This module
supplies the two helpers that enforce the contract:

* :func:`hash_filename` — SHA-256 over the **basename** only. Never
  hashes the parent directory because leaking
  ``/Users/dr-smith/patient_042/slide_a.svs`` as a stable hash would
  still partially identify a patient via the parent path token.
* :func:`strip_phi` — walks a caller-supplied params dict and drops
  any key whose name suggests a filesystem path. The remaining dict
  is safe to serialise into ``runs.metrics_json``.

Both helpers are pure. No IO, no network, no stdlib beyond
``hashlib`` + ``pathlib``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = [
    "PHI_PARAM_KEYS",
    "hash_filename",
    "redact_manifest_path",
    "strip_phi",
]


PHI_PARAM_KEYS: frozenset[str] = frozenset(
    {
        "path",
        "filename",
        "file_path",
        "filepath",
        "tile_path",
        "image_path",
        "input_path",
        "output_path",
        "source_path",
        "source",
        "input",
        "output",
        "dir",
        "directory",
        "folder",
        "image",
        "tile",
        "file",
    }
)
"""Keys that :func:`strip_phi` removes from params dicts.

Membership is checked case-insensitively. Deliberately generous —
dropping a borderline key costs us nothing (the caller has other ways
to surface it), while leaking one is a safety-v1 regression.
"""


def hash_filename(path: str | Path) -> str:
    """Return the SHA-256 of the **basename** of ``path``.

    Input may be a ``str`` or a :class:`pathlib.Path`. Empty input
    hashes the empty string. The return value is hex (64 chars).

    Example
    -------
    >>> h = hash_filename("/Users/dr-smith/phi/CaseA.svs")
    >>> h == hash_filename("CaseA.svs")  # parent path is stripped
    True
    """
    text = str(path)
    basename = Path(text).name if text else ""
    return hashlib.sha256(basename.encode("utf-8")).hexdigest()


def redact_manifest_path(path: str | Path) -> str:
    """PHI-safe representation of a manifest file path.

    The ``runs.manifest_path`` column in ``audit.db`` is load-bearing
    for debuggability ("where did this run's manifest land?") but a
    raw absolute path can encode patient context via parent
    directories (``/Users/dr-smith/patient_042/runs/…``). We strip the
    parent and replace it with a stable 8-char hash so two runs from
    the same directory still collate, without the directory itself
    landing in plaintext.

    Empty input is passed through unchanged. The output is
    ``"<basename>#<sha256-of-parent[:8]>"`` for non-empty input and
    always shorter than 128 chars.
    """
    text = str(path)
    if not text:
        return ""
    p = Path(text)
    basename = p.name or text
    parent = str(p.parent) if p.parent != p else ""
    parent_hash = hashlib.sha256(parent.encode("utf-8")).hexdigest()[:8]
    return f"{basename}#{parent_hash}"


def _looks_like_path(value: Any) -> bool:
    """Is ``value`` plausibly a filesystem path we must redact?"""
    if isinstance(value, Path):
        return True
    if not isinstance(value, str):
        return False
    # Anything starting with a leading slash / tilde / drive letter is
    # almost certainly a filesystem path — even if the key is innocent.
    if value.startswith(("/", "~")):
        return True
    return len(value) >= 3 and value[1:3] == ":\\"


def strip_phi(params: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a shallow copy of ``params`` with path-like keys removed.

    The check is on **keys** (by name, case-insensitive against
    :data:`PHI_PARAM_KEYS`) **and** on **values** (anything that looks
    like a filesystem path gets replaced with the placeholder
    ``"<redacted-path>"``). Nested dicts are recursively cleaned.

    Non-mapping inputs pass through unchanged. ``None`` returns an
    empty dict so callers can safely `json.dumps` the result.
    """
    if params is None:
        return {}
    if not isinstance(params, Mapping):
        raise TypeError(f"strip_phi expects a Mapping or None, got {type(params).__name__}")

    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        key_str = str(key)
        if key_str.lower() in PHI_PARAM_KEYS:
            continue
        if isinstance(value, Mapping):
            cleaned[key_str] = strip_phi(value)
            continue
        if isinstance(value, (list, tuple)):
            cleaned[key_str] = [
                strip_phi(item) if isinstance(item, Mapping) else _redact_value(item)
                for item in value
            ]
            continue
        cleaned[key_str] = _redact_value(value)
    return cleaned


def _redact_value(value: Any) -> Any:
    if _looks_like_path(value):
        return "<redacted-path>"
    return value
