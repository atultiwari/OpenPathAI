"""``openpathai methods write`` — MedGemma-drafted Methods paragraph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from openpathai.nl import (
    LLMUnavailableError,
    default_llm_backend_registry,
    detect_default_backend,
)
from openpathai.nl.methods_writer import (
    MethodsWriterError,
    write_methods,
)

__all__ = ["methods_app"]

methods_app = typer.Typer(
    name="methods",
    help="Draft copy-pasteable Methods paragraphs from a run manifest (Phase 17).",
)


@methods_app.command("write")
def write_cmd(
    manifest_path: Annotated[
        Path,
        typer.Argument(help="Path to a run manifest JSON."),
    ],
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Optional path to write the Methods paragraph as Markdown."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Override the LLM model id (defaults to the backend default).",
        ),
    ] = None,
) -> None:
    """Draft a Methods paragraph for ``manifest_path``."""
    if not manifest_path.exists():
        typer.secho(
            f"manifest not found: {manifest_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.secho(
            f"manifest is not valid JSON: {exc!s}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc

    try:
        backend = detect_default_backend(registry=default_llm_backend_registry())
    except LLMUnavailableError as exc:
        typer.secho(str(exc), fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=3) from exc
    if model is not None:
        backend.model = model  # type: ignore[misc]

    try:
        paragraph = write_methods(payload, backend=backend)
    except MethodsWriterError as exc:
        typer.secho(
            f"Methods draft failed: {exc!s}\nLast LLM output:\n{exc.last_output}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(paragraph.text + "\n", encoding="utf-8")

    typer.echo(
        json.dumps(
            {
                "manifest_run_id": paragraph.manifest_run_id,
                "manifest_graph_hash": paragraph.manifest_graph_hash,
                "cited_datasets": list(paragraph.cited_datasets),
                "cited_models": list(paragraph.cited_models),
                "backend_id": paragraph.backend_id,
                "model_id": paragraph.model_id,
                "attempts": paragraph.attempts,
                "generated_at": paragraph.generated_at,
                "prompt_hash": paragraph.prompt_hash,
                "text_path": str(out) if out is not None else None,
            },
            indent=2,
            sort_keys=True,
        )
    )
    typer.echo("\n--- drafted paragraph ---\n" + paragraph.text, err=True)
