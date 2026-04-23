"""``openpathai models`` subcommand — inspect the Tier-A model zoo."""

from __future__ import annotations

from typing import Annotated

import typer

models_app = typer.Typer(
    name="models",
    help="Inspect the Tier-A model zoo.",
    no_args_is_help=True,
    add_completion=False,
)


@models_app.command("list")
def list_models(
    family: Annotated[
        str | None,
        typer.Option(help="Filter by family (resnet, vit, swin, ...)."),
    ] = None,
    framework: Annotated[
        str | None,
        typer.Option(help="Filter by framework (timm, huggingface, ...)."),
    ] = None,
    tier: Annotated[
        str | None,
        typer.Option(help="Filter by compute tier (T1, T2, T3)."),
    ] = None,
) -> None:
    """List every registered model card, optionally filtered."""
    from openpathai.models import default_model_registry

    registry = default_model_registry()
    cards = registry.filter(
        family=family,  # type: ignore[arg-type]
        framework=framework,  # type: ignore[arg-type]
        tier=tier,
    )
    if not cards:
        typer.echo("(no model cards matched)")
        raise typer.Exit(0)
    for card in cards:
        typer.echo(
            f"{card.name:36s}  family={card.family:<10s}  "
            f"params={card.num_params_m:6.1f}M  license={card.source.license}"
        )


__all__ = ["models_app"]
