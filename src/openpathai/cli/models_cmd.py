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


@models_app.command("check")
def check_models() -> None:
    """Validate every registered model card against the Phase 7 contract.

    Exits non-zero when any card fails. Prints a table of every card
    (passes and fails) so CI and humans can see the full state.
    """
    from openpathai.models import default_model_registry
    from openpathai.safety import validate_card

    registry = default_model_registry()
    failures = 0

    valid_names = registry.names()
    invalid_names = registry.invalid_names()
    all_names = sorted({*valid_names, *invalid_names})

    if not all_names:
        typer.echo("(no model cards registered)")
        raise typer.Exit(1)

    for name in all_names:
        card = registry.get(name) if name in valid_names else registry.invalid_card(name)
        issues = validate_card(card)
        if issues:
            failures += 1
            typer.secho(f"FAIL {name}", fg="red")
            for issue in issues:
                typer.echo(f"    [{issue.code}] {issue.message}")
        else:
            typer.secho(f"ok   {name}", fg="green")

    if failures:
        typer.secho(
            f"\n{failures} model card(s) failed the safety contract.",
            fg="red",
            err=True,
        )
        raise typer.Exit(2)


__all__ = ["models_app"]
