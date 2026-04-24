"""Structured diff of two audit runs.

The CLI (`openpathai diff RUN_A RUN_B`) and the GUI Runs tab both
consume the same :class:`RunDiff` so the diff is defined exactly once.
Colour / ANSI rendering lives in the CLI module — this module stays
pure so it can be unit-tested without a TTY.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "FieldDelta",
    "RunDiff",
    "diff_dicts",
    "diff_runs",
]


@dataclass(frozen=True, slots=True)
class FieldDelta:
    """One changed field between two runs.

    Attributes
    ----------
    field:
        Dotted path; scalar fields read as ``"status"``, nested JSON
        values read as ``"metrics_json.accuracy"``.
    before:
        Value in the "A" run (``None`` when missing).
    after:
        Value in the "B" run (``None`` when missing).
    kind:
        ``"added"`` (only in B), ``"removed"`` (only in A), or
        ``"changed"`` (both but different).
    """

    field: str
    before: Any
    after: Any
    kind: str  # "added" | "removed" | "changed"


@dataclass(frozen=True, slots=True)
class RunDiff:
    """Structured diff result.

    Attributes
    ----------
    run_id_a, run_id_b:
        The two run ids compared.
    deltas:
        Every :class:`FieldDelta` (changed + added + removed).
    unchanged:
        Field paths that matched exactly. Only populated when the
        caller passes ``include_unchanged=True`` to :func:`diff_runs`.
    """

    run_id_a: str
    run_id_b: str
    deltas: tuple[FieldDelta, ...]
    unchanged: tuple[str, ...] = field(default_factory=tuple)

    def is_empty(self) -> bool:
        """Whether the two runs are byte-equal on every diffed field."""
        return not self.deltas


# --- Internals -------------------------------------------------------------

_DIFFED_SCALAR_FIELDS: tuple[str, ...] = (
    "kind",
    "mode",
    "timestamp_start",
    "timestamp_end",
    "pipeline_yaml_hash",
    "graph_hash",
    "git_commit",
    "tier",
    "status",
    "manifest_path",
)


def diff_dicts(
    a: dict[str, Any] | None,
    b: dict[str, Any] | None,
    *,
    prefix: str = "",
) -> list[FieldDelta]:
    """Shallow-diff two dicts (one level of nesting). Pure helper.

    Used internally to crack ``metrics_json`` open so callers see
    per-metric deltas instead of two JSON blobs.
    """
    a_dict = a or {}
    b_dict = b or {}
    deltas: list[FieldDelta] = []
    keys = sorted(set(a_dict) | set(b_dict))
    for key in keys:
        field_name = f"{prefix}{key}" if prefix else key
        if key in a_dict and key not in b_dict:
            deltas.append(
                FieldDelta(
                    field=field_name,
                    before=a_dict[key],
                    after=None,
                    kind="removed",
                )
            )
        elif key not in a_dict and key in b_dict:
            deltas.append(
                FieldDelta(
                    field=field_name,
                    before=None,
                    after=b_dict[key],
                    kind="added",
                )
            )
        elif a_dict[key] != b_dict[key]:
            deltas.append(
                FieldDelta(
                    field=field_name,
                    before=a_dict[key],
                    after=b_dict[key],
                    kind="changed",
                )
            )
    return deltas


def _parse_metrics_json(blob: str | None) -> dict[str, Any]:
    if not blob:
        return {}
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def diff_runs(
    a: Any,
    b: Any,
    *,
    include_unchanged: bool = False,
) -> RunDiff:
    """Return a :class:`RunDiff` comparing two run entries.

    Accepts any object exposing the public fields of
    :class:`openpathai.safety.audit.db.AuditEntry` via attribute
    access (``.run_id``, ``.kind``, ``.metrics_json``, …). The loose
    typing keeps the helper usable from tests that fixture up a plain
    dataclass without importing the full DB module.
    """
    run_id_a = str(getattr(a, "run_id", ""))
    run_id_b = str(getattr(b, "run_id", ""))

    deltas: list[FieldDelta] = []
    unchanged: list[str] = []

    for field_name in _DIFFED_SCALAR_FIELDS:
        a_val = getattr(a, field_name, None)
        b_val = getattr(b, field_name, None)
        if a_val == b_val:
            unchanged.append(field_name)
            continue
        deltas.append(
            FieldDelta(
                field=field_name,
                before=a_val,
                after=b_val,
                kind="changed"
                if a_val is not None and b_val is not None
                else ("added" if a_val is None else "removed"),
            )
        )

    # Crack metrics_json open so per-metric deltas surface.
    a_metrics = _parse_metrics_json(getattr(a, "metrics_json", None))
    b_metrics = _parse_metrics_json(getattr(b, "metrics_json", None))
    nested = diff_dicts(a_metrics, b_metrics, prefix="metrics_json.")
    for delta in nested:
        deltas.append(delta)
    for key in sorted(set(a_metrics) & set(b_metrics)):
        if a_metrics[key] == b_metrics[key]:
            unchanged.append(f"metrics_json.{key}")

    return RunDiff(
        run_id_a=run_id_a,
        run_id_b=run_id_b,
        deltas=tuple(deltas),
        unchanged=tuple(unchanged) if include_unchanged else (),
    )
