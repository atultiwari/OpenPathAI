"""``openpathai run PIPELINE.yaml`` — execute a pipeline from a YAML file."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Annotated

import typer

from openpathai.cli.pipeline_yaml import PipelineYamlError, load_pipeline
from openpathai.pipeline.cache import ContentAddressableCache, default_cache_root
from openpathai.pipeline.executor import Executor


def register(app: typer.Typer) -> None:
    @app.command()
    def run(
        pipeline_path: Annotated[
            Path,
            typer.Argument(help="Path to a pipeline YAML file.", exists=True, dir_okay=False),
        ],
        output_dir: Annotated[
            Path | None,
            typer.Option(
                "--output-dir",
                help="Where to write the manifest JSON. Defaults to ./runs/<run-id>/.",
            ),
        ] = None,
        cache_root: Annotated[
            Path | None,
            typer.Option(
                "--cache-root",
                help="Cache directory (defaults to ~/.openpathai/cache/).",
            ),
        ] = None,
    ) -> None:
        """Execute a pipeline YAML via the Phase 1 executor."""
        try:
            pipeline = load_pipeline(pipeline_path)
        except PipelineYamlError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(2) from exc

        cache = ContentAddressableCache(root=cache_root or default_cache_root())
        executor = Executor(cache)
        result = executor.run(pipeline)

        destination = output_dir or Path("runs") / str(uuid.uuid4())
        destination.mkdir(parents=True, exist_ok=True)
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(result.manifest.to_json(indent=2), encoding="utf-8")
        artifact_summary = {
            step_id: {
                "artifact_type": artifact.artifact_type,
                "content_hash": artifact.content_hash(),
            }
            for step_id, artifact in result.artifacts.items()
        }
        (destination / "artifacts.json").write_text(
            json.dumps(artifact_summary, indent=2),
            encoding="utf-8",
        )
        typer.echo(
            f"pipeline={pipeline.id}  steps={len(result.step_records)}  "
            f"hits={result.cache_stats.hits} misses={result.cache_stats.misses}"
        )
        typer.echo(f"manifest: {manifest_path}")


__all__ = ["register"]
