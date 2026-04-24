"""``openpathai serve`` — launch the Phase-19 FastAPI backend.

FastAPI + uvicorn live in the ``[server]`` extra and are imported
lazily inside :func:`_launch`; the CLI shim itself does not pull
them so users without the extra still get a clean error.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer

from openpathai.server.config import DEFAULT_PORT, ServerSettings, generate_token


def _resolve_token(cli_token: str | None) -> str:
    if cli_token:
        return cli_token
    env = os.environ.get("OPENPATHAI_API_TOKEN")
    if env:
        return env
    token = generate_token()
    typer.secho(
        f"[openpathai serve] auto-generated bearer token: {token}",
        fg=typer.colors.YELLOW,
        err=True,
    )
    typer.secho(
        "  Pass --token <value> or set OPENPATHAI_API_TOKEN to pin it.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    return token


def register(app: typer.Typer) -> None:
    @app.command()
    def serve(
        host: Annotated[
            str,
            typer.Option(help="Bind address. Defaults to 127.0.0.1 (loopback)."),
        ] = "127.0.0.1",
        port: Annotated[
            int,
            typer.Option(min=1, max=65535, help=f"Port. Defaults to {DEFAULT_PORT}."),
        ] = DEFAULT_PORT,
        token: Annotated[
            str | None,
            typer.Option(
                "--token",
                help=(
                    "Bearer token for every /v1 endpoint except /v1/health. "
                    "Falls back to OPENPATHAI_API_TOKEN or a fresh random token."
                ),
            ),
        ] = None,
        cors_origin: Annotated[
            list[str] | None,
            typer.Option(
                "--cors-origin",
                help="Additional allowed CORS origin. Repeatable.",
            ),
        ] = None,
        openpathai_home: Annotated[
            Path | None,
            typer.Option(
                "--home",
                help="Override OPENPATHAI_HOME for this process.",
            ),
        ] = None,
        reload: Annotated[
            bool,
            typer.Option("--reload", help="Enable uvicorn auto-reload (dev only)."),
        ] = False,
        log_level: Annotated[
            str,
            typer.Option(help="uvicorn log level."),
        ] = "info",
    ) -> None:
        """Launch the OpenPathAI FastAPI backend (Phase 19).

        Requires the ``[server]`` extra (``uv sync --extra server``).
        """
        try:
            import uvicorn

            from openpathai.server.app import create_app
            from openpathai.server.config import DEFAULT_CORS_ORIGINS
        except ImportError as exc:  # pragma: no cover - import-time error path
            typer.secho(
                "[openpathai serve] the `server` extra is not installed. "
                "Run `uv sync --extra server` (or pip install 'openpathai[server]').",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(3) from exc

        resolved_token = _resolve_token(token)
        origins: tuple[str, ...] = tuple(cors_origin) if cors_origin else DEFAULT_CORS_ORIGINS
        settings_kwargs: dict[str, object] = {
            "host": host,
            "port": port,
            "token": resolved_token,
            "cors_origins": origins,
        }
        if openpathai_home is not None:
            settings_kwargs["openpathai_home"] = openpathai_home
        settings = ServerSettings(**settings_kwargs)  # type: ignore[arg-type]
        app = create_app(settings)
        typer.secho(
            f"[openpathai serve] http://{settings.host}:{settings.port}/v1/health",
            fg=typer.colors.GREEN,
            err=True,
        )
        uvicorn.run(  # pragma: no cover - network launch
            app,
            host=settings.host,
            port=settings.port,
            log_level=log_level,
            reload=reload,
        )


__all__ = ["register"]
