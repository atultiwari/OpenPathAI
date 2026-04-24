"""``openpathai llm`` — probe local LLM backends (Ollama + LM Studio)."""

from __future__ import annotations

import subprocess
import sys
from typing import Annotated

import typer

from openpathai.nl import (
    LLMUnavailableError,
    default_llm_backend_registry,
    detect_default_backend,
)

__all__ = ["llm_app"]

llm_app = typer.Typer(
    name="llm",
    help="Probe + install local LLM backends (Ollama, LM Studio).",
)


@llm_app.command("status")
def status_cmd() -> None:
    """Probe every registered backend and print a status table."""
    reg = default_llm_backend_registry()
    rows: list[tuple[str, ...]] = [
        ("id", "base_url", "model", "reachable"),
    ]
    for backend in reg:
        reachable = backend.probe()
        rows.append(
            (
                backend.id,
                backend.base_url,
                backend.model,
                "yes" if reachable else "no",
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for r, row in enumerate(rows):
        typer.echo("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        if r == 0:
            typer.echo("  ".join("-" * w for w in widths))

    try:
        active = detect_default_backend(registry=reg)
    except LLMUnavailableError as exc:
        typer.secho(f"\nNo backend is reachable.\n{exc!s}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(f"\nactive backend: {active.id} ({active.base_url} / {active.model})")


@llm_app.command("pull")
def pull_cmd(
    model: Annotated[str, typer.Argument(help="Ollama model id (e.g. 'medgemma:1.5').")],
) -> None:
    """Shell out to ``ollama pull <model>`` when ollama is installed."""
    # Check the ``ollama`` CLI is on PATH.
    try:
        subprocess.run(  # pragma: no cover - interactive
            ["ollama", "--version"], check=True, capture_output=True, timeout=5
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        typer.secho(
            f"ollama CLI not found on PATH. Install from https://ollama.com "
            f"and rerun `openpathai llm pull {model}`.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=3) from exc
    typer.echo(f"Running: ollama pull {model}")
    try:  # pragma: no cover - interactive
        subprocess.run(["ollama", "pull", model], check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover
        typer.secho(f"ollama pull failed: {exc!s}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Pulled {model}. Run `openpathai llm status` to verify.", err=True)
    sys.stdout.flush()
