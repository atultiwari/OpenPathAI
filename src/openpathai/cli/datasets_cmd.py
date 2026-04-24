"""``openpathai datasets`` — list / inspect / register dataset cards.

Phase 7 extends the original list + show surface with three new
commands that round out the "local-first datasets" story:

* ``datasets register`` — scan an ImageFolder tree, write a local card.
* ``datasets deregister`` — delete a user card.
* ``datasets list --source local/shipped/all`` — restrict the listing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from openpathai.data import default_registry, deregister_folder, list_local, register_folder
from openpathai.data.registry import DatasetRegistry

datasets_app = typer.Typer(
    name="datasets",
    help="List, inspect, and register dataset cards (shipped or user-supplied).",
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


def _source_for(name: str) -> str:
    """Return ``"local"`` if ``name`` is user-registered, else ``"shipped"``."""
    for card in list_local():
        if card.name == name:
            return "local"
    return "shipped"


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
    source: Annotated[
        str,
        typer.Option(
            help="Show shipped cards, local (user-registered) cards, or both.",
            case_sensitive=False,
        ),
    ] = "all",
) -> None:
    """List every registered dataset card, optionally filtered."""
    src = source.strip().lower()
    if src not in {"all", "shipped", "local"}:
        typer.secho(
            f"--source must be one of all/shipped/local (got {source!r}).",
            fg="red",
            err=True,
        )
        raise typer.Exit(2)

    if src == "local":
        registry: DatasetRegistry = DatasetRegistry(include_repo=False)
    elif src == "shipped":
        registry = DatasetRegistry(include_user=False)
    else:
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
        origin = _source_for(card.name) if src == "all" else src
        typer.echo(
            f"{card.name:18s}  modality={card.modality:<4s}  "
            f"classes={card.num_classes:>3d}  "
            f"{_size_blurb(card.download.size_gb)}  "
            f"{gated}  src={origin:<7s}  {card.license}"
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
    typer.echo(yaml.safe_dump(card.model_dump(mode="json"), sort_keys=False))


@datasets_app.command("register")
def register_dataset(
    path: Annotated[Path, typer.Argument(help="Root of the ImageFolder tree.")],
    name: Annotated[str, typer.Option(help="Card name (e.g. mini_demo).")],
    tissue: Annotated[
        list[str],
        typer.Option("--tissue", help="Tissue tag (repeatable)."),
    ],
    modality: Annotated[
        str,
        typer.Option(help="Modality (tile; wsi is deferred to Phase 9)."),
    ] = "tile",
    display_name: Annotated[
        str | None,
        typer.Option(help="Pretty display name (defaults to --name)."),
    ] = None,
    license: Annotated[
        str,
        typer.Option(help="Licence identifier."),
    ] = "user-supplied",
    stain: Annotated[str, typer.Option(help="Stain label.")] = "H&E",
    overwrite: Annotated[
        bool,
        typer.Option(help="Replace an existing card of the same name."),
    ] = False,
) -> None:
    """Register a local ImageFolder-style tree as a dataset card."""
    if modality == "wsi":
        typer.secho(
            "WSI registration is deferred to Phase 9. Use --modality tile.",
            fg="red",
            err=True,
        )
        raise typer.Exit(2)
    try:
        card = register_folder(
            path,
            name=name,
            tissue=tuple(tissue),
            modality="tile",
            display_name=display_name,
            license=license,
            stain=stain,
            overwrite=overwrite,
        )
    except FileExistsError as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(2) from exc
    except (NotADirectoryError, ValueError) as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(2) from exc
    typer.secho(
        f"Registered {card.name} ({card.num_classes} classes, {card.total_images} images).",
        fg="green",
    )


@datasets_app.command("deregister")
def deregister_dataset(
    name: Annotated[str, typer.Argument(help="Card name to remove.")],
) -> None:
    """Delete a user-registered card (never touches shipped cards)."""
    if deregister_folder(name):
        typer.secho(f"Deregistered {name}.", fg="green")
    else:
        typer.secho(f"No local card named {name!r}.", fg="yellow", err=True)
        raise typer.Exit(1)


__all__ = ["datasets_app"]
