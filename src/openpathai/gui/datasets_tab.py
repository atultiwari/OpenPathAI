"""Datasets tab — filter + inspect + register user folders.

Phase 7 expansions:

* New **source** column so users can tell at a glance whether a card was
  shipped with the repo or added locally.
* New **Add local dataset** accordion — wraps
  :func:`openpathai.data.register_folder` as a callback.
* New **Deregister** button + input, for removing the local cards the
  accordion writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpathai.data import (
    default_registry,
    deregister_folder,
    register_folder,
)
from openpathai.data.registry import DatasetRegistry
from openpathai.gui.views import datasets_rows, local_sources

DATASETS_HEADERS = [
    "name",
    "display_name",
    "modality",
    "tissue",
    "classes",
    "size",
    "gated",
    "confirm",
    "source",
    "license",
]


def _rows_as_list(  # pragma: no cover - gradio
    *,
    modality: str | None = None,
    tissue: str | None = None,
    tier: str | None = None,
) -> list[list[str]]:
    """Shape the view-model rows into gradio's DataFrame layout."""
    rows = datasets_rows(modality=modality, tissue=tissue, tier=tier)
    if not rows:
        return []
    return [[row[key] for key in DATASETS_HEADERS] for row in rows]


def _yaml_for(name: str) -> str:  # pragma: no cover - gradio
    import yaml

    if not default_registry().has(name):
        return f"# {name} is not registered."
    return yaml.safe_dump(default_registry().get(name).model_dump(mode="json"), sort_keys=False)


def _register_local(  # pragma: no cover - gradio
    path: str,
    name: str,
    tissue_csv: str,
    license_field: str,
    stain: str,
    overwrite: bool,
) -> tuple[list[list[str]], str]:
    """Register an ImageFolder-style tree as a local dataset card."""
    path = (path or "").strip()
    name = (name or "").strip()
    tissue_csv = (tissue_csv or "").strip()
    if not path or not name or not tissue_csv:
        return _rows_as_list(), (
            "Please set path, name, and at least one tissue tag before submitting."
        )

    tissue = tuple(part.strip() for part in tissue_csv.split(",") if part.strip())
    if not tissue:
        return _rows_as_list(), "Please provide at least one tissue tag."

    try:
        card = register_folder(
            Path(path),
            name=name,
            tissue=tissue,
            modality="tile",
            license=license_field.strip() or "user-supplied",
            stain=stain.strip() or "H&E",
            overwrite=bool(overwrite),
        )
    except (FileExistsError, NotADirectoryError, ValueError) as exc:
        return _rows_as_list(), f"Register failed: {exc}"

    # Refresh the table so the new card is visible immediately.
    # The default_registry() is a process-wide singleton, so we reload a
    # fresh DatasetRegistry to pick up the new YAML without dropping the
    # existing shipped entries.
    rows = datasets_rows(registry=DatasetRegistry())
    return (
        [[row[key] for key in DATASETS_HEADERS] for row in rows],
        f"Registered {card.name} ({card.num_classes} classes, {card.total_images} images).",
    )


def _deregister_local(name: str) -> tuple[list[list[str]], str]:  # pragma: no cover - gradio
    name = (name or "").strip()
    if not name:
        return _rows_as_list(), "Enter a local card name to deregister."
    if name not in local_sources():
        return (
            _rows_as_list(),
            f"{name!r} is not a local card; only user-registered cards can be deregistered.",
        )
    if deregister_folder(name):
        rows = datasets_rows(registry=DatasetRegistry())
        return (
            [[row[key] for key in DATASETS_HEADERS] for row in rows],
            f"Deregistered {name}.",
        )
    return _rows_as_list(), f"Nothing to deregister: {name!r} not found."


def build(state: Any) -> Any:  # pragma: no cover - gradio-gated renderer
    """Render the Datasets tab. ``state`` is the shared :class:`AppState`."""
    import gradio as gr

    del state  # Read-only tab; no state mutation.
    with gr.Blocks() as tab:
        gr.Markdown("### Dataset registry")
        with gr.Row():
            modality = gr.Dropdown(["", "tile", "wsi"], value="", label="Modality filter")
            tissue = gr.Textbox(label="Tissue filter (e.g. lung)", value="")
            tier = gr.Dropdown(["", "T1", "T2", "T3"], value="", label="Tier filter")
        refresh = gr.Button("Refresh")
        table = gr.Dataframe(
            headers=DATASETS_HEADERS,
            value=_rows_as_list(),
            interactive=False,
        )

        def _filter(m: str, t: str, tier_opt: str) -> list[list[str]]:
            return _rows_as_list(
                modality=m or None,
                tissue=t or None,
                tier=tier_opt or None,
            )

        refresh.click(_filter, inputs=[modality, tissue, tier], outputs=[table])

        with gr.Accordion("Add local dataset", open=False):
            gr.Markdown(
                "Register an ImageFolder-style tree so it appears in the "
                "table above. Each sub-directory under **Folder path** "
                "becomes a class. Supported extensions: `.png .jpg .jpeg "
                "`.tif .tiff`."
            )
            with gr.Row():
                reg_path = gr.Textbox(label="Folder path", value="")
                reg_name = gr.Textbox(label="Card name (e.g. my_demo)", value="")
            with gr.Row():
                reg_tissue = gr.Textbox(
                    label="Tissue tag(s) — comma-separated (e.g. colon, breast)",
                    value="",
                )
                reg_license = gr.Textbox(label="Licence", value="user-supplied")
                reg_stain = gr.Textbox(label="Stain", value="H&E")
                reg_overwrite = gr.Checkbox(label="Overwrite existing card", value=False)
            reg_submit = gr.Button("Register local dataset")
            reg_status = gr.Markdown("")
            reg_submit.click(
                _register_local,
                inputs=[
                    reg_path,
                    reg_name,
                    reg_tissue,
                    reg_license,
                    reg_stain,
                    reg_overwrite,
                ],
                outputs=[table, reg_status],
            )

        with gr.Accordion("Deregister local dataset", open=False):
            with gr.Row():
                dereg_name = gr.Textbox(label="Local card name", value="")
                dereg_submit = gr.Button("Deregister")
            dereg_status = gr.Markdown("")
            dereg_submit.click(
                _deregister_local,
                inputs=[dereg_name],
                outputs=[table, dereg_status],
            )

        gr.Markdown("### Inspect a card")
        with gr.Row():
            name = gr.Textbox(label="Dataset name", value="kather_crc_5k")
            show_btn = gr.Button("Show YAML")
        yaml_box = gr.Code(language="yaml", label="YAML")
        show_btn.click(_yaml_for, inputs=[name], outputs=[yaml_box])
    return tab


__all__ = ["DATASETS_HEADERS", "build"]
