"""``openpathai download`` — dataset fetcher with size confirmation UX."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from openpathai.data import default_registry
from openpathai.data.downloaders import (
    MissingBackendError,
    describe_download,
    dispatch_download,
)


def register(app: typer.Typer) -> None:
    @app.command()
    def download(
        name: Annotated[str, typer.Argument(help="Registered dataset name.")],
        yes: Annotated[
            bool,
            typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
        ] = False,
        subset: Annotated[
            int | None,
            typer.Option(
                "--subset",
                min=1,
                help="POC fetch: pull the first N files / slides only.",
            ),
        ] = None,
        root: Annotated[
            Path | None,
            typer.Option(
                "--root",
                help="Override the download root. Defaults to ~/.openpathai/datasets/.",
            ),
        ] = None,
    ) -> None:
        """Download a registered dataset.

        Prints the size warning and (for gated sources) the access
        instructions. A full fetch requires ``--yes`` so no large
        transfer ever starts by accident.
        """
        registry = default_registry()
        if not registry.has(name):
            typer.secho(
                f"Dataset {name!r} is not registered.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        card = registry.get(name)

        typer.echo(describe_download(card))

        if card.download.method == "manual":
            typer.echo("")
            typer.echo("This dataset is manual-only — follow the instructions above.")
            raise typer.Exit(0)

        if not yes and card.download.should_confirm_before_download:
            typer.secho(
                "\nAborting — pass --yes to confirm this download.",
                fg=typer.colors.YELLOW,
            )
            raise typer.Exit(2)

        if card.download.gated and not yes:
            typer.secho(
                "\nAborting — gated access. Re-run with --yes once you have "
                "permission and have logged in.",
                fg=typer.colors.YELLOW,
            )
            raise typer.Exit(2)

        try:
            result = dispatch_download(card, root=root, subset=subset)
        except MissingBackendError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(3) from exc
        except NotImplementedError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(4) from exc
        typer.echo(f"\ndone — wrote {result.files_written} file(s) to {result.target_dir}")


__all__ = ["register"]
