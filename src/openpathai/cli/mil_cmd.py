"""``openpathai mil`` — list registered MIL aggregators."""

from __future__ import annotations

import typer

from openpathai.mil import default_mil_registry

__all__ = ["mil_app"]

mil_app = typer.Typer(
    name="mil",
    help="Multiple-Instance Learning aggregators (Phase 13).",
)


@mil_app.command("list")
def list_cmd() -> None:
    """List every registered MIL aggregator."""
    reg = default_mil_registry(embedding_dim=384, num_classes=2)
    header = ("id", "status")
    rows: list[tuple[str, str]] = [header]
    for name in reg.names():
        agg = reg.get(name)
        # Stubs define an internal _promotion_note attribute; real
        # adapters don't.
        is_stub = hasattr(agg, "_promotion_note")
        rows.append((name, "stub" if is_stub else "shipped"))
    widths = [max(len(r[i]) for r in rows) for i in range(2)]
    for r, row in enumerate(rows):
        typer.echo(f"{row[0].ljust(widths[0])}  {row[1].ljust(widths[1])}")
        if r == 0:
            typer.echo(f"{'-' * widths[0]}  {'-' * widths[1]}")
