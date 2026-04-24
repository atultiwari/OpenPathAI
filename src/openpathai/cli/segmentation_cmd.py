"""``openpathai segmentation`` — list + resolve segmentation adapters."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from openpathai.segmentation import (
    default_segmentation_registry,
    resolve_segmenter,
)

__all__ = ["segmentation_app"]

segmentation_app = typer.Typer(
    name="segmentation",
    help="Segmentation adapter registry + fallback resolver.",
)


@segmentation_app.command("list")
def list_cmd() -> None:
    """List every registered segmentation adapter (closed + promptable)."""
    reg = default_segmentation_registry()
    rows: list[tuple[str, ...]] = [
        ("id", "kind", "gated", "weight_source"),
    ]
    for adapter in reg:
        rows.append(
            (
                adapter.id,
                "promptable" if adapter.promptable else "closed",
                "yes" if adapter.gated else "no",
                adapter.weight_source or "—",
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for r, row in enumerate(rows):
        typer.echo("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        if r == 0:
            typer.echo("  ".join("-" * w for w in widths))


@segmentation_app.command("resolve")
def resolve_cmd(
    segmenter_id: Annotated[
        str,
        typer.Argument(help="Segmentation adapter id (e.g. 'medsam2')."),
    ],
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Disable fallback; hard-fail on gated access."),
    ] = False,
) -> None:
    """Resolve ``segmenter_id`` and print the ``FallbackDecision`` as JSON."""
    reg = default_segmentation_registry()
    try:
        decision = resolve_segmenter(segmenter_id, registry=reg, allow_fallback=not strict)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(json.dumps(decision.model_dump(), indent=2, sort_keys=True))
