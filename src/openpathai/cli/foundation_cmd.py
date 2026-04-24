"""``openpathai foundation`` — list and resolve foundation backbones.

Two subcommands in Phase 13:

* ``foundation list``   — tabular print of every registered adapter
  (id, display name, gated flag, embedding dim, HF repo, license).
* ``foundation resolve <id>`` — run the fallback resolver and print
  the resulting :class:`FallbackDecision` as JSON.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from openpathai.foundation import (
    default_foundation_registry,
    resolve_backbone,
)

__all__ = ["foundation_app"]

foundation_app = typer.Typer(
    name="foundation",
    help="Foundation-backbone registry + gated-access fallback resolver.",
)


@foundation_app.command("list")
def list_cmd() -> None:
    """List every registered foundation backbone."""
    reg = default_foundation_registry()
    rows: list[tuple[str, ...]] = [
        ("id", "gated", "embed_dim", "hf_repo", "license"),
    ]
    for adapter in reg:
        rows.append(
            (
                adapter.id,
                "yes" if adapter.gated else "no",
                str(adapter.embedding_dim),
                adapter.hf_repo or "—",
                adapter.license,
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for r, row in enumerate(rows):
        line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        typer.echo(line)
        if r == 0:
            typer.echo("  ".join("-" * w for w in widths))


@foundation_app.command("resolve")
def resolve_cmd(
    backbone_id: Annotated[
        str,
        typer.Argument(help="Foundation backbone id to resolve (e.g. 'uni')."),
    ],
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Disable fallback; hard-fail on gated access.",
        ),
    ] = False,
) -> None:
    """Resolve ``backbone_id`` and print the ``FallbackDecision`` as JSON."""
    reg = default_foundation_registry()
    try:
        decision = resolve_backbone(backbone_id, registry=reg, allow_fallback=not strict)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(json.dumps(decision.model_dump(), indent=2, sort_keys=True))
