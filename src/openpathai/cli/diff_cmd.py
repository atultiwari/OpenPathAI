"""``openpathai diff <run_a> <run_b>`` — colour-coded parameter diff.

Reads two :class:`AuditEntry` rows from the audit DB and prints a
side-by-side diff. ANSI colour only when stdout is a TTY (and
``NO_COLOR`` is unset); plain text when piped so grep / diff / sed all
work.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:  # pragma: no cover - type-only import
    from openpathai.safety.audit.diff import FieldDelta

__all__ = ["register"]


def _use_colour() -> bool:
    """True when stdout is a TTY and NO_COLOR is unset."""
    if os.environ.get("NO_COLOR", "").strip():
        return False
    return sys.stdout.isatty()


_ANSI: dict[str, str] = {
    "added": "\x1b[32m",
    "removed": "\x1b[31m",
    "changed": "\x1b[33m",
    "reset": "\x1b[0m",
}


def _colour(text: str, kind: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{_ANSI.get(kind, '')}{text}{_ANSI['reset']}"


def _format_value(value: object) -> str:
    if value is None:
        return "—"
    text = str(value)
    # Guardrail — truncate very long hashes so the table stays readable.
    if len(text) > 60:
        return text[:28] + "…" + text[-28:]
    return text


def _render(deltas: tuple[FieldDelta, ...], run_a: str, run_b: str, *, colour: bool) -> str:
    if not deltas:
        return f"No changes between {run_a} and {run_b}."
    lines: list[str] = []
    header = f"{'field':<34s}  {run_a[:18]:<20s}  {run_b[:18]:<20s}"
    lines.append(header)
    lines.append("-" * len(header))
    for delta in deltas:
        before = _format_value(delta.before)
        after = _format_value(delta.after)
        row = f"{delta.field:<34s}  {before:<20s}  {after:<20s}"
        lines.append(_colour(row, delta.kind, colour))
    return "\n".join(lines)


def register(app: typer.Typer) -> None:
    @app.command()
    def diff(
        run_a: Annotated[str, typer.Argument(help="First run id.")],
        run_b: Annotated[str, typer.Argument(help="Second run id.")],
        show_unchanged: Annotated[
            bool,
            typer.Option(
                "--show-unchanged/--no-show-unchanged",
                help="Also list fields that matched exactly.",
            ),
        ] = False,
    ) -> None:
        """Print a colour-coded diff of two audit runs."""
        from openpathai.safety.audit import AuditDB, diff_runs

        db = AuditDB.open_default()
        entry_a = db.get_run(run_a)
        entry_b = db.get_run(run_b)
        missing = [name for name, e in (("run_a", entry_a), ("run_b", entry_b)) if e is None]
        if missing:
            typer.secho(f"No audit entry for: {', '.join(missing)}", fg="red", err=True)
            raise typer.Exit(2)
        assert entry_a is not None  # narrow for type checker
        assert entry_b is not None
        diff_result = diff_runs(entry_a, entry_b, include_unchanged=show_unchanged)
        typer.echo(
            _render(
                diff_result.deltas,
                diff_result.run_id_a,
                diff_result.run_id_b,
                colour=_use_colour(),
            )
        )
        if show_unchanged and diff_result.unchanged:
            typer.echo("")
            typer.echo(f"Unchanged ({len(diff_result.unchanged)}):")
            for field in diff_result.unchanged:
                typer.echo(f"  {field}")
