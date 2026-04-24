"""``openpathai run PIPELINE.yaml`` — execute a pipeline from a YAML file.

Phase 10 extends the original run with three new flags:

* ``--workers N``                — thread-pool size for parallel execution.
* ``--parallel-mode {sequential,thread}`` — topology. ``sequential``
  (default) preserves Phase 1 behaviour.
* ``--snakefile PATH``           — export-only. Writes a Snakefile
  equivalent of the pipeline and exits **without** executing it.
"""

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
        workers: Annotated[
            int | None,
            typer.Option(
                "--workers",
                min=1,
                help=(
                    "Thread-pool size when --parallel-mode=thread. "
                    "Overrides any pipeline-level max_workers hint."
                ),
            ),
        ] = None,
        parallel_mode: Annotated[
            str,
            typer.Option(
                "--parallel-mode",
                help="Execution topology: 'sequential' (default) or 'thread'.",
                case_sensitive=False,
            ),
        ] = "sequential",
        snakefile: Annotated[
            Path | None,
            typer.Option(
                "--snakefile",
                help=(
                    "Export-only: write a Snakefile to this path and exit "
                    "without executing the pipeline."
                ),
            ),
        ] = None,
        no_audit: Annotated[
            bool,
            typer.Option(
                "--no-audit",
                help="Skip the Phase 8 audit log write for this run.",
            ),
        ] = False,
    ) -> None:
        """Execute a pipeline YAML via the Phase 1 executor."""
        try:
            pipeline = load_pipeline(pipeline_path)
        except PipelineYamlError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(2) from exc

        # Export-only path — no execution, no audit.
        if snakefile is not None:
            from openpathai.pipeline.snakemake import write_snakefile

            target = write_snakefile(pipeline, snakefile)
            typer.secho(f"Wrote Snakefile → {target}", fg="green")
            typer.echo(
                f"Run with `snakemake --snakefile {target} --cores N` "
                "(requires the `[snakemake]` extra)."
            )
            return

        mode = parallel_mode.strip().lower()
        if mode not in {"sequential", "thread"}:
            typer.secho(
                f"--parallel-mode must be 'sequential' or 'thread', got {parallel_mode!r}.",
                fg="red",
                err=True,
            )
            raise typer.Exit(2)

        effective_workers = workers if workers is not None else pipeline.max_workers

        cache = ContentAddressableCache(root=cache_root or default_cache_root())
        executor = Executor(
            cache,
            max_workers=effective_workers,
            parallel_mode=mode,  # type: ignore[arg-type]
        )
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
        parallel_blurb = (
            f"parallel=thread workers={effective_workers or 1}"
            if mode == "thread"
            else "parallel=sequential"
        )
        typer.echo(
            f"pipeline={pipeline.id}  steps={len(result.step_records)}  "
            f"hits={result.cache_stats.hits} misses={result.cache_stats.misses}  "
            f"{parallel_blurb}"
        )
        typer.echo(f"manifest: {manifest_path}")

        if not no_audit:
            from openpathai.safety.audit import log_pipeline

            run_id = log_pipeline(result.manifest, manifest_path=str(manifest_path))
            if run_id:
                typer.echo(f"audit: {run_id}")


__all__ = ["register"]
