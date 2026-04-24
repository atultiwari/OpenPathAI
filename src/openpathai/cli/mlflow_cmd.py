"""``openpathai mlflow-ui`` — launch the MLflow UI against the local
``$OPENPATHAI_HOME/mlruns`` directory.

Thin subprocess launcher so we never import mlflow at module load
time. Exits with a friendly install reminder when the ``[mlflow]``
extra is absent.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from typing import Annotated

import typer

__all__ = ["register"]


def register(app: typer.Typer) -> None:
    @app.command("mlflow-ui")
    def mlflow_ui(
        host: Annotated[
            str,
            typer.Option(help="Bind host for the MLflow UI."),
        ] = "127.0.0.1",
        port: Annotated[
            int,
            typer.Option(help="Bind port for the MLflow UI.", min=1, max=65535),
        ] = 5000,
        tracking_uri: Annotated[
            str | None,
            typer.Option(
                "--tracking-uri",
                help=(
                    "Override the tracking URI. Defaults to "
                    "file://$OPENPATHAI_HOME/mlruns (or $MLFLOW_TRACKING_URI)."
                ),
            ),
        ] = None,
    ) -> None:
        """Launch the MLflow UI against the OpenPathAI tracking store.

        Requires the ``[mlflow]`` extra. The invocation is a
        ``subprocess.run`` of ``mlflow ui --host … --port …`` so the
        UI inherits stdout/stderr and Ctrl-C stops it cleanly.
        """
        if importlib.util.find_spec("mlflow") is None:
            typer.secho(
                "mlflow-ui requires the `mlflow` package. "
                "Install via the [mlflow] extra: `uv sync --extra mlflow`.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(3)

        from openpathai.pipeline.mlflow_backend import default_mlflow_uri

        uri = tracking_uri or default_mlflow_uri()
        cmd = [
            sys.executable,
            "-m",
            "mlflow",
            "ui",
            "--host",
            host,
            "--port",
            str(port),
            "--backend-store-uri",
            uri,
        ]
        typer.echo(f"Launching: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=False)  # pragma: no cover - interactive
        except KeyboardInterrupt:  # pragma: no cover - interactive
            typer.echo("mlflow-ui stopped.")
