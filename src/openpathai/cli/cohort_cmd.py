"""``openpathai cohort`` — build + QC a cohort (Phase 9).

Subcommands:

* ``cohort build <path>``   — scan a directory into a cohort YAML.
* ``cohort qc <cohort.yaml>`` — run QC on every slide and render
  HTML / PDF reports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

cohort_app = typer.Typer(
    name="cohort",
    help="Build and QC cohorts (Phase 9).",
    no_args_is_help=True,
    add_completion=False,
)


@cohort_app.command("build")
def build_cohort(
    directory: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Directory to scan for WSI files.",
        ),
    ],
    cohort_id: Annotated[
        str,
        typer.Option("--id", help="Cohort id (stable string key)."),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help="Where to write the cohort YAML.",
        ),
    ],
    pattern: Annotated[
        str | None,
        typer.Option(help="Optional glob pattern (e.g. '*.svs')."),
    ] = None,
) -> None:
    """Scan a directory for slide files and write a cohort YAML."""
    from openpathai.io import Cohort

    try:
        cohort = Cohort.from_directory(directory, cohort_id, pattern=pattern)
    except (NotADirectoryError, ValueError) as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(2) from exc
    cohort.to_yaml(output)
    typer.secho(
        f"Wrote cohort {cohort_id} with {len(cohort)} slide(s) to {output}.",
        fg="green",
    )


@cohort_app.command("qc")
def run_cohort_qc(
    cohort_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Cohort YAML file.",
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Where to write the QC report."),
    ] = Path("cohort-qc"),
    pdf: Annotated[
        bool,
        typer.Option("--pdf/--no-pdf", help="Also write a PDF report."),
    ] = False,
    thumbnail_size: Annotated[
        int,
        typer.Option(
            min=64,
            max=8192,
            help="Long-edge thumbnail size in pixels.",
        ),
    ] = 1024,
) -> None:
    """Run QC on every slide in a cohort YAML."""
    import numpy as np

    from openpathai.io import Cohort, open_slide
    from openpathai.preprocessing.qc import render_html, render_pdf

    try:
        cohort = Cohort.from_yaml(cohort_path)
    except (ValueError, FileNotFoundError) as exc:
        typer.secho(f"Failed to load cohort: {exc}", fg="red", err=True)
        raise typer.Exit(2) from exc

    output_dir.mkdir(parents=True, exist_ok=True)

    def _extract_thumbnail(slide) -> np.ndarray:
        try:
            with open_slide(slide.path) as reader:
                info = reader.info
                # Read the top-of-pyramid level; the pillow backend
                # downsamples the whole image. The PIL resize below
                # trims to ``thumbnail_size`` on the long edge.
                region = reader.read_region(
                    location=(0, 0),
                    size=(info.width, info.height),
                    level=info.level_count - 1 if info.level_count > 1 else 0,
                )
            arr = np.asarray(region, dtype=np.uint8)
            # Resize down to thumbnail_size on the long edge.
            from PIL import Image

            pil = Image.fromarray(arr[..., :3])
            ratio = thumbnail_size / max(pil.width, pil.height)
            if ratio < 1.0:
                new_size = (
                    max(1, int(pil.width * ratio)),
                    max(1, int(pil.height * ratio)),
                )
                pil = pil.resize(new_size, Image.Resampling.BILINEAR)
            return np.asarray(pil, dtype=np.uint8)
        except Exception as exc:
            typer.secho(
                f"Warning: thumbnail extraction failed for {slide.slide_id}: {exc}. "
                "Substituting a mid-grey thumbnail so QC still runs.",
                fg="yellow",
                err=True,
            )
            return np.full((thumbnail_size, thumbnail_size, 3), 200, dtype=np.uint8)

    report = cohort.run_qc(_extract_thumbnail)
    summary = report.summary()
    typer.echo(
        f"cohort={cohort.id}  pass={summary['pass']}  "
        f"warn={summary['warn']}  fail={summary['fail']}"
    )

    html_path = output_dir / "cohort-qc.html"
    render_html(report, html_path)
    typer.echo(f"html: {html_path}")

    if pdf:
        pdf_path = output_dir / "cohort-qc.pdf"
        render_pdf(report, pdf_path)
        typer.echo(f"pdf:  {pdf_path}")


__all__ = ["cohort_app"]
