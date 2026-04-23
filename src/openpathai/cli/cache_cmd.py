"""``openpathai cache`` — introspect and clean the content-addressable cache."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Annotated

import typer

from openpathai.pipeline.cache import ContentAddressableCache, default_cache_root

cache_app = typer.Typer(
    name="cache",
    help="Inspect and clear the OpenPathAI content-addressable cache.",
    no_args_is_help=True,
    add_completion=False,
)


def _iter_entries(root: Path):
    if not root.is_dir():
        return
    for child in sorted(root.iterdir()):
        if child.is_dir():
            yield child


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for sub in path.rglob("*"):
        if sub.is_file():
            with contextlib.suppress(OSError):
                total += sub.stat().st_size
    return total


@cache_app.command("show")
def show(
    cache_root: Annotated[
        Path | None,
        typer.Option("--cache-root", help="Cache directory."),
    ] = None,
) -> None:
    """Print cache root, entry count, and total size on disk."""
    root = cache_root or default_cache_root()
    typer.echo(f"cache_root: {root}")
    entries = list(_iter_entries(root))
    typer.echo(f"entries:    {len(entries)}")
    total = sum(_dir_size_bytes(entry) for entry in entries)
    typer.echo(f"total_size: {total / (1024 * 1024):.2f} MiB")


@cache_app.command("clear")
def clear(
    cache_root: Annotated[
        Path | None,
        typer.Option("--cache-root", help="Cache directory."),
    ] = None,
    older_than_days: Annotated[
        int | None,
        typer.Option(
            "--older-than-days",
            min=0,
            help="Only clear entries whose meta.created_at is older than N days.",
        ),
    ] = None,
) -> None:
    """Remove every cache entry (or only those older than ``--older-than-days``)."""
    cache = ContentAddressableCache(root=cache_root or default_cache_root())
    removed = cache.clear(older_than_days=older_than_days)
    typer.echo(f"removed {removed} cache entr{'y' if removed == 1 else 'ies'}")


@cache_app.command("invalidate")
def invalidate(
    key: Annotated[str, typer.Argument(help="The SHA-256 cache key to drop.")],
    cache_root: Annotated[
        Path | None,
        typer.Option("--cache-root", help="Cache directory."),
    ] = None,
) -> None:
    """Drop a single cache entry by key."""
    cache = ContentAddressableCache(root=cache_root or default_cache_root())
    ok = cache.invalidate(key)
    if ok:
        typer.echo(f"invalidated {key}")
    else:
        typer.echo(f"no entry found for {key}", err=True)
        raise typer.Exit(1)


__all__ = ["cache_app"]
