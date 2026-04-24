"""``openpathai detection`` — list + resolve detection adapters."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from openpathai.detection import default_detection_registry, resolve_detector

__all__ = ["detection_app"]

detection_app = typer.Typer(
    name="detection",
    help="Object-detection adapter registry + fallback resolver.",
)


@detection_app.command("list")
def list_cmd() -> None:
    """List every registered detection adapter."""
    reg = default_detection_registry()
    rows: list[tuple[str, ...]] = [
        ("id", "gated", "weight_source", "license"),
    ]
    for adapter in reg:
        rows.append(
            (
                adapter.id,
                "yes" if adapter.gated else "no",
                adapter.weight_source or "—",
                adapter.license,
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for r, row in enumerate(rows):
        typer.echo("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        if r == 0:
            typer.echo("  ".join("-" * w for w in widths))


@detection_app.command("resolve")
def resolve_cmd(
    detector_id: Annotated[
        str,
        typer.Argument(help="Detection adapter id (e.g. 'yolov26')."),
    ],
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Disable fallback; hard-fail on gated access."),
    ] = False,
) -> None:
    """Resolve ``detector_id`` and print the ``FallbackDecision`` as JSON."""
    reg = default_detection_registry()
    try:
        decision = resolve_detector(detector_id, registry=reg, allow_fallback=not strict)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(json.dumps(decision.model_dump(), indent=2, sort_keys=True))
