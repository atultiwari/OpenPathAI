"""OpenPathAI CLI entry point.

Phase 0 registers only ``--version`` and a ``hello`` smoke command. Real
sub-commands (``train``, ``analyse``, ``run``, ``download``, ``export-colab``,
``gui``, ``nl``, ``cache``, ``mlflow-ui``) arrive in the phases that deliver
them; each one is a thin wrapper over a library function.
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
    # Intentionally empty: the --version flag is handled eagerly by the
    # callback above; this function exists so Typer treats --version as a
    # root-level option rather than requiring a sub-command.
    del version  # silence unused-argument warnings


@app.command()
def hello() -> None:
    """Phase 0 smoke command — prints a liveness message."""
    typer.echo("Phase 0 foundation is live.")


if __name__ == "__main__":  # pragma: no cover
    app()
