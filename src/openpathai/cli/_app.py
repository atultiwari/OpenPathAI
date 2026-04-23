"""Root Typer app + top-level callbacks.

This module exists so every subcommand can import ``app`` without
pulling the whole CLI graph back through :mod:`openpathai.cli.main`.
"""

from __future__ import annotations

import typer

from openpathai import __version__

app = typer.Typer(
    name="openpathai",
    help="OpenPathAI — computational pathology workflow environment.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(0)


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print the OpenPathAI version and exit.",
    ),
) -> None:
    """Root callback wiring ``--version`` to the top-level command."""
    del version


@app.command()
def hello() -> None:
    """Phase 0 smoke command — prints a liveness message."""
    typer.echo("Phase 0 foundation is live.")


__all__ = ["app"]
