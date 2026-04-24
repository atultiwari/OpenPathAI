"""``openpathai export-colab`` + ``openpathai sync`` (Phase 11)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

__all__ = ["register"]


def register(app: typer.Typer) -> None:
    @app.command("export-colab")
    def export_colab(
        out: Annotated[
            Path,
            typer.Option(
                "--out",
                help="Where to write the generated .ipynb.",
            ),
        ],
        pipeline_path: Annotated[
            Path | None,
            typer.Option(
                "--pipeline",
                help="Pipeline YAML file to embed in the notebook.",
                exists=True,
                dir_okay=False,
            ),
        ] = None,
        run_id: Annotated[
            str | None,
            typer.Option(
                "--run-id",
                help=(
                    "Audit run id to use as lineage. Either --pipeline or "
                    "--run-id must be supplied."
                ),
            ),
        ] = None,
        openpathai_version: Annotated[
            str | None,
            typer.Option(
                "--openpathai-version",
                help="Pin the install cell to this OpenPathAI version.",
            ),
        ] = None,
    ) -> None:
        """Render a Colab reproduction notebook for a pipeline."""
        if pipeline_path is None and run_id is None:
            typer.secho(
                "Pass --pipeline PATH or --run-id <id> (or both).",
                fg="red",
                err=True,
            )
            raise typer.Exit(2)

        from openpathai.cli.pipeline_yaml import PipelineYamlError, load_pipeline
        from openpathai.export import ColabExportError, render_notebook, write_notebook

        pipeline = None
        if pipeline_path is not None:
            try:
                pipeline = load_pipeline(pipeline_path)
            except PipelineYamlError as exc:
                typer.secho(str(exc), fg="red", err=True)
                raise typer.Exit(2) from exc

        audit_entry = None
        if run_id is not None:
            from openpathai.safety.audit import AuditDB

            db = AuditDB.open_default()
            audit_entry = db.get_run(run_id)
            if audit_entry is None:
                typer.secho(
                    f"No audit run with id {run_id!r}. Run `openpathai audit list` "
                    "to see available ids, or omit --run-id.",
                    fg="red",
                    err=True,
                )
                raise typer.Exit(2)

        if pipeline is None and audit_entry is not None:
            # No explicit --pipeline, but the audit row points at a manifest_path;
            # we don't store the YAML itself so the CLI requires --pipeline for
            # the round-trip. Surface a clear diagnostic.
            typer.secho(
                "--run-id alone is not enough to embed the pipeline YAML — the "
                "audit row stores the manifest hash, not the YAML itself. Pass "
                "--pipeline PATH pointing at the YAML that produced the run.",
                fg="red",
                err=True,
            )
            raise typer.Exit(2)

        try:
            notebook = render_notebook(
                pipeline=pipeline,
                audit_entry=audit_entry,
                openpathai_version=openpathai_version,
            )
        except ColabExportError as exc:
            typer.secho(str(exc), fg="red", err=True)
            raise typer.Exit(2) from exc

        target = write_notebook(notebook, out)
        typer.secho(f"Wrote Colab notebook → {target}", fg="green")

    @app.command("sync")
    def sync(
        manifest_path: Annotated[
            Path,
            typer.Argument(
                help="Path to a RunManifest JSON file (e.g. downloaded from Colab).",
                exists=True,
                dir_okay=False,
            ),
        ],
        show: Annotated[
            bool,
            typer.Option(
                "--show",
                help="Print the audit row that would be inserted; do not write.",
            ),
        ] = False,
    ) -> None:
        """Import a RunManifest JSON file into the local audit DB."""
        from openpathai.safety.audit import (
            ManifestImportError,
            import_manifest,
            preview_manifest,
        )

        try:
            if show:
                preview = preview_manifest(manifest_path)
                typer.echo(json.dumps(preview, indent=2, sort_keys=True, default=str))
                return
            entry = import_manifest(manifest_path)
        except ManifestImportError as exc:
            typer.secho(str(exc), fg="red", err=True)
            raise typer.Exit(2) from exc

        typer.secho(
            f"Imported run {entry.run_id} (kind={entry.kind}, status={entry.status}).",
            fg="green",
        )
