"""Cohorts tab — load / build / QC cohorts from the browser (Phase 9).

Every callback delegates to :class:`openpathai.io.Cohort` helpers or
to :func:`openpathai.preprocessing.qc.render_html` / ``render_pdf``
so this module stays thin.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from openpathai.gui.views import cohort_rows
from openpathai.safety.audit.phi import redact_manifest_path

COHORT_HEADERS: list[str] = [
    "slide_id",
    "patient_id",
    "label",
    "path",
    "mpp",
    "magnification",
]


def _rows_for(path: str) -> tuple[list[list[str]], str]:  # pragma: no cover - gradio
    rows = cohort_rows(path)
    if not rows:
        return [], "Load a cohort YAML or build one below."
    return (
        [[row[key] for key in COHORT_HEADERS] for row in rows],
        f"Loaded {len(rows)} slide(s).",
    )


def _build_from_directory(  # pragma: no cover - gradio
    directory: str,
    cohort_id: str,
    pattern: str,
    output: str,
) -> tuple[list[list[str]], str]:
    directory = (directory or "").strip()
    cohort_id = (cohort_id or "").strip()
    output = (output or "").strip()
    if not directory or not cohort_id or not output:
        return [], "Provide directory + cohort id + output path."
    from openpathai.io import Cohort

    try:
        cohort = Cohort.from_directory(
            directory,
            cohort_id,
            pattern=pattern.strip() or None,
        )
        cohort.to_yaml(output)
    except (NotADirectoryError, ValueError) as exc:
        return [], f"Build failed: {exc}"
    rows, status = _rows_for(output)
    # Iron rule #8: never render absolute patient-context paths in the
    # GUI. ``redact_manifest_path`` keeps the basename so users still see
    # which YAML was written, but hashes the parent directory.
    return rows, f"{status}  Wrote cohort YAML → {redact_manifest_path(output)}."


def _fake_thumbnail(shape: tuple[int, int, int] = (256, 256, 3)) -> np.ndarray:
    """Fallback mid-grey thumbnail for slides we can't open."""
    return np.full(shape, 200, dtype=np.uint8)


def _thumbnail_for(slide, thumb_size: int):  # pragma: no cover - gradio
    from PIL import Image

    from openpathai.io import open_slide

    try:
        with open_slide(slide.path) as reader:
            info = reader.info
            level = info.level_count - 1 if info.level_count > 1 else 0
            region = reader.read_region(
                location=(0, 0),
                size=(info.width, info.height),
                level=level,
            )
        arr = np.asarray(region, dtype=np.uint8)[..., :3]
        pil = Image.fromarray(arr)
        ratio = thumb_size / max(pil.width, pil.height)
        if ratio < 1.0:
            size = (max(1, int(pil.width * ratio)), max(1, int(pil.height * ratio)))
            pil = pil.resize(size, Image.Resampling.BILINEAR)
        return np.asarray(pil, dtype=np.uint8)
    except Exception:
        return _fake_thumbnail()


def _run_qc(  # pragma: no cover - gradio
    path: str,
    thumb_size: int,
    want_pdf: bool,
    output_dir: str,
) -> tuple[str, str | None, str | None, dict[str, int]]:
    path = (path or "").strip()
    output_dir = (output_dir or "").strip()
    if not path:
        return (
            "Enter a cohort YAML path first.",
            None,
            None,
            {"pass": 0, "warn": 0, "fail": 0},
        )
    from openpathai.io import Cohort
    from openpathai.preprocessing.qc import render_html, render_pdf

    try:
        cohort = Cohort.from_yaml(path)
    except (ValueError, FileNotFoundError) as exc:
        return (f"Load failed: {exc}", None, None, {"pass": 0, "warn": 0, "fail": 0})

    report = cohort.run_qc(lambda slide: _thumbnail_for(slide, int(thumb_size)))
    out_root = Path(output_dir) if output_dir else Path(path).parent / "cohort-qc"
    out_root.mkdir(parents=True, exist_ok=True)
    html_path = render_html(report, out_root / "cohort-qc.html")
    pdf_path = render_pdf(report, out_root / "cohort-qc.pdf") if want_pdf else None

    summary = report.summary()
    safe_html = redact_manifest_path(html_path)
    safe_pdf = redact_manifest_path(pdf_path) if pdf_path else None
    status = (
        f"QC complete. pass={summary['pass']}  warn={summary['warn']}  "
        f"fail={summary['fail']}.  HTML → {safe_html}"
    )
    if safe_pdf:
        status += f"  PDF → {safe_pdf}"
    return status, safe_html, safe_pdf, summary


def build(state: Any) -> Any:  # pragma: no cover - gradio-gated renderer
    import gradio as gr

    del state
    with gr.Blocks() as tab:
        gr.Markdown(
            "### Cohorts (Phase 9)\n"
            "A cohort is a named group of slides. Load an existing "
            "cohort YAML, build one from a directory, or run QC on the "
            "slides — HTML + PDF reports are written next to the YAML."
        )

        with gr.Row():
            path_box = gr.Textbox(label="Cohort YAML path", value="")
            load_btn = gr.Button("Load")
        load_status = gr.Markdown("")
        slides_table = gr.Dataframe(headers=COHORT_HEADERS, interactive=False)
        load_btn.click(_rows_for, inputs=[path_box], outputs=[slides_table, load_status])

        with gr.Accordion("Build cohort from directory", open=False):
            with gr.Row():
                build_dir = gr.Textbox(label="Directory", value="")
                build_id = gr.Textbox(label="Cohort id", value="")
            with gr.Row():
                build_pattern = gr.Textbox(label="Glob pattern (optional)", value="")
                build_output = gr.Textbox(label="Output YAML path", value="")
            build_btn = gr.Button("Build + save")
            build_status = gr.Markdown("")
            build_btn.click(
                _build_from_directory,
                inputs=[build_dir, build_id, build_pattern, build_output],
                outputs=[slides_table, build_status],
            )

        with gr.Accordion("Run QC on the loaded cohort", open=False):
            with gr.Row():
                thumb_size = gr.Slider(
                    minimum=256,
                    maximum=4096,
                    step=128,
                    value=1024,
                    label="Thumbnail long-edge",
                )
                want_pdf = gr.Checkbox(label="Also write PDF", value=False)
                qc_output = gr.Textbox(
                    label="Output directory (defaults to cohort YAML parent)",
                    value="",
                )
            qc_btn = gr.Button("Run QC")
            qc_status = gr.Markdown("")
            qc_summary = gr.JSON(label="Summary")
            with gr.Row():
                qc_html = gr.Textbox(label="HTML report path", interactive=False)
                qc_pdf = gr.Textbox(label="PDF report path", interactive=False)
            qc_btn.click(
                _run_qc,
                inputs=[path_box, thumb_size, want_pdf, qc_output],
                outputs=[qc_status, qc_html, qc_pdf, qc_summary],
            )
    return tab


__all__ = ["COHORT_HEADERS", "build"]
