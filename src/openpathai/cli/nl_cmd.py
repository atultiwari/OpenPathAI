"""``openpathai nl`` — natural-language zero-shot + pipeline draft."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import numpy as np
import typer
from PIL import Image

from openpathai.cli.pipeline_yaml import dump_pipeline
from openpathai.nl import (
    LLMUnavailableError,
    classify_zero_shot,
    default_llm_backend_registry,
    detect_default_backend,
    draft_pipeline_from_prompt,
    segment_text_prompt,
)
from openpathai.nl.pipeline_gen import PipelineDraftError

__all__ = ["nl_app"]

nl_app = typer.Typer(
    name="nl",
    help="Natural-language zero-shot classification + segmentation + pipeline draft.",
)


def _load_image(path: Path) -> np.ndarray:
    if not path.exists():
        raise typer.BadParameter(f"image not found: {path}")
    img = Image.open(path).convert("RGB")
    return np.asarray(img)


@nl_app.command("classify")
def classify_cmd(
    image: Annotated[Path, typer.Argument(help="Path to the tile / image to classify.")],
    prompt: Annotated[
        list[str],
        typer.Option(
            "--prompt",
            help="Repeatable — at least 2 prompts needed for softmax.",
        ),
    ],
    backbone: Annotated[
        str, typer.Option("--backbone", help="Backbone id (default: conch).")
    ] = "conch",
    temperature: Annotated[
        float,
        typer.Option("--temperature", help="Softmax temperature.", min=0.1),
    ] = 100.0,
) -> None:
    """Zero-shot classify ``image`` against ``--prompt`` candidates."""
    if len(prompt) < 2:
        typer.secho(
            "at least two --prompt values are required for zero-shot softmax",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    arr = _load_image(image)
    result = classify_zero_shot(
        arr,
        prompts=prompt,
        temperature=temperature,
        backbone_id=backbone,
    )
    typer.echo(json.dumps(result.model_dump(), indent=2, sort_keys=True))


@nl_app.command("segment")
def segment_cmd(
    image: Annotated[Path, typer.Argument(help="Path to the tile / image to segment.")],
    prompt: Annotated[str, typer.Option("--prompt", help="Single text prompt, e.g. 'gland'.")],
    segmenter: Annotated[
        str,
        typer.Option("--segmenter", help="Promptable segmenter id (default: medsam2)."),
    ] = "medsam2",
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Optional mask PNG output path."),
    ] = None,
) -> None:
    """Text-prompted segmentation on ``image``."""
    if not prompt.strip():
        typer.secho("--prompt must be non-empty", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    arr = _load_image(image)
    result = segment_text_prompt(arr, prompt=prompt, segmenter_id=segmenter)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        mask = result.mask.array
        # Scale label ids into 0..255 for a visible PNG.
        scaled = (
            (mask * (255 // max(mask.max(), 1))).astype(np.uint8)
            if mask.max() > 0
            else mask.astype(np.uint8)
        )
        Image.fromarray(scaled, mode="L").save(out)
    typer.echo(
        json.dumps(
            {
                "model_id": result.model_id,
                "resolved_model_id": result.resolved_model_id,
                "mask_shape": list(result.mask.array.shape),
                "class_names": list(result.mask.class_names),
                "metadata": dict(result.metadata),
                "mask_png": str(out) if out is not None else None,
            },
            indent=2,
            sort_keys=True,
        )
    )


@nl_app.command("draft")
def draft_cmd(
    prompt: Annotated[str, typer.Argument(help="Free-text pipeline description.")],
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Optional path to write the drafted YAML."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Override the LLM model id (defaults to backend default).",
        ),
    ] = None,
) -> None:
    """Draft a :class:`Pipeline` YAML from ``prompt`` via MedGemma."""
    try:
        backend = detect_default_backend(registry=default_llm_backend_registry())
    except LLMUnavailableError as exc:
        typer.secho(str(exc), fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=3) from exc
    if model is not None:
        backend.model = model  # override  # type: ignore[misc]
    try:
        draft = draft_pipeline_from_prompt(prompt, backend=backend)
    except PipelineDraftError as exc:
        typer.secho(
            f"Pipeline draft failed: {exc!s}\nLast LLM output:\n{exc.last_output}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc

    yaml_text = dump_pipeline(draft.pipeline)  # canonicalise
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml_text, encoding="utf-8")

    # Iron rule #8: never print the raw prompt in CLI stdout. If the
    # user piped in a path-containing prompt (slide paths, patient
    # folders) it would land in CI logs / terminal scrollback. The
    # ``prompt_hash`` is enough to correlate with the audit record.
    typer.echo(
        json.dumps(
            {
                "prompt_hash": draft.prompt_hash,
                "backend_id": draft.backend_id,
                "model_id": draft.model_id,
                "generated_at": draft.generated_at,
                "attempts": draft.attempts,
                "pipeline_id": draft.pipeline.id,
                "yaml_path": str(out) if out is not None else None,
            },
            indent=2,
            sort_keys=True,
        )
    )
    typer.echo("\n--- drafted YAML ---\n" + yaml_text, err=True)
