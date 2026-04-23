"""Datasets tab — filter + inspect every registered dataset card."""

from __future__ import annotations

from typing import Any

from openpathai.data import default_registry
from openpathai.gui.views import datasets_rows


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
    keys = list(rows[0].keys())
    return [[row[key] for key in keys] for row in rows]


def _yaml_for(name: str) -> str:  # pragma: no cover - gradio
    import yaml

    if not default_registry().has(name):
        return f"# {name} is not registered."
    return yaml.safe_dump(default_registry().get(name).model_dump(), sort_keys=False)


def build(state: Any) -> None:  # pragma: no cover - gradio-gated renderer
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
        headers = [
            "name",
            "display_name",
            "modality",
            "tissue",
            "classes",
            "size",
            "gated",
            "confirm",
            "license",
        ]
        table = gr.Dataframe(headers=headers, value=_rows_as_list(), interactive=False)

        def _filter(m: str, t: str, tier_opt: str) -> list[list[str]]:
            return _rows_as_list(
                modality=m or None,
                tissue=t or None,
                tier=tier_opt or None,
            )

        refresh.click(_filter, inputs=[modality, tissue, tier], outputs=[table])

        gr.Markdown("### Inspect a card")
        with gr.Row():
            name = gr.Textbox(label="Dataset name", value="lc25000")
            show_btn = gr.Button("Show YAML")
        yaml_box = gr.Code(language="yaml", label="YAML")
        show_btn.click(_yaml_for, inputs=[name], outputs=[yaml_box])
    return tab


__all__ = ["build"]
