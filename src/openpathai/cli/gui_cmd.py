"""``openpathai gui`` — launch the Gradio app.

Gradio is lazy-imported inside :func:`launch_app`; this CLI shim
exists only to wire Typer options onto the function call. If the
``[gui]`` extra is absent the command exits 3 with an install
reminder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from openpathai.gui.state import AppState


def register(app: typer.Typer) -> None:
    @app.command()
    def gui(
        host: Annotated[
            str,
            typer.Option(help="Bind address. Defaults to 127.0.0.1 (localhost)."),
        ] = "127.0.0.1",
        port: Annotated[
            int,
            typer.Option(min=0, help="Port. Defaults to 7860 (Gradio default)."),
        ] = 7860,
        share: Annotated[
            bool,
            typer.Option(
                "--share",
                help="Publish via Gradio's tunnel. Off by default.",
            ),
        ] = False,
        cache_root: Annotated[
            Path | None,
            typer.Option("--cache-root", help="Override the cache root."),
        ] = None,
        device: Annotated[
            str,
            typer.Option(help="Default device (auto / cpu / cuda / mps)."),
        ] = "auto",
    ) -> None:
        """Launch the OpenPathAI Gradio app.

        Requires the ``[gui]`` extra (``uv sync --extra gui``). The
        default bind is ``127.0.0.1:7860``; pass ``--share`` to open a
        Gradio tunnel.
        """
        try:
            from openpathai.gui.app import launch_app
        except ImportError as exc:  # pragma: no cover - import always succeeds
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(3) from exc

        state = AppState(
            host=host,
            port=port,
            share=share,
            cache_root=cache_root or AppState().cache_root,
            device=device,
        )
        try:
            launch_app(state)  # pragma: no cover - network launch
        except ImportError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(3) from exc


__all__ = ["register"]
