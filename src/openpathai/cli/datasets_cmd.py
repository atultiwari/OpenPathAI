"""``openpathai datasets`` — list + inspect registered dataset cards."""

from __future__ import annotations

from typing import Annotated

import typer
import yaml

from openpathai.data import default_registry

datasets_app = typer.Typer(
    name="datasets",
    help="List and inspect registered dataset cards.",
    no_args_is_help=True,
    add_completion=False,
)


def _size_blurb(size_gb: float | None) -> str:
    if size_gb is None:
        return "size=?   "
    if size_gb >= 100:
        return f"size={size_gb:>6.0f}G"
    if size_gb >= 1.0:
        return f"size={size_gb:>6.1f}G"
    return f"size={size_gb * 1024:>5.0f}M"


@datasets_app.command("list")
def list_datasets(
    modality: Annotated[
        str | None,
        typer.Option(help="Filter by modality (tile / wsi)."),
    ] = None,
    tissue: Annotated[
        str | None,
        typer.Option(help="Filter by tissue (e.g. lung, breast)."),
    ] = None,
    tier: Annotated[
        str | None,
        typer.Option(help="Filter by compute tier (T1, T2, T3)."),
    ] = None,
) -> None:
    """List every registered dataset card."""
    registry = default_registry()
    cards = registry.filter(
        modality=modality,  # type: ignore[arg-type]
        tissue=tissue,
        tier=tier,
    )
    if not cards:
        typer.echo("(no dataset cards matched)")
        raise typer.Exit(0)
    for card in cards:
        gated = "gated" if card.download.gated else "open "
        typer.echo(
            f"{card.name:18s}  modality={card.modality:<4s}  "
            f"classes={card.num_classes:>3d}  "
            f"{_size_blurb(card.download.size_gb)}  "
            f"{gated}  {card.license}"
        )


@datasets_app.command("show")
def show_dataset(
    name: Annotated[str, typer.Argument(help="Dataset card name.")],
) -> None:
    """Print the full dataset card YAML."""
    registry = default_registry()
    if not registry.has(name):
        typer.echo(f"Dataset {name!r} is not registered.", err=True)
        raise typer.Exit(2)
    card = registry.get(name)
    typer.echo(yaml.safe_dump(card.model_dump(), sort_keys=False))


__all__ = ["datasets_app"]
