"""Models tab — filter + inspect every registered model card."""

from __future__ import annotations

from typing import Any

from openpathai.gui.views import models_rows


def _rows_as_list(  # pragma: no cover - gradio
    *,
    family: str | None = None,
    framework: str | None = None,
    tier: str | None = None,
) -> list[list[str]]:
    rows = models_rows(family=family, framework=framework, tier=tier)
    if not rows:
        return []
    keys = list(rows[0].keys())
    return [[row[key] for key in keys] for row in rows]


def build(state: Any) -> None:  # pragma: no cover - gradio-gated renderer
    import gradio as gr

    del state
    with gr.Blocks() as tab:
        gr.Markdown("### Model registry (Tier A)")
        with gr.Row():
            family = gr.Textbox(label="Family filter (resnet, vit, ...)", value="")
            framework = gr.Textbox(label="Framework filter", value="")
            tier = gr.Dropdown(["", "T1", "T2", "T3"], value="", label="Tier filter")
        refresh = gr.Button("Refresh")
        headers = [
            "name",
            "display_name",
            "family",
            "framework",
            "params_m",
            "input_size",
            "license",
            "gated",
        ]
        table = gr.Dataframe(headers=headers, value=_rows_as_list(), interactive=False)

        def _filter(fam: str, fw: str, tier_opt: str) -> list[list[str]]:
            return _rows_as_list(
                family=fam or None,
                framework=fw or None,
                tier=tier_opt or None,
            )

        refresh.click(_filter, inputs=[family, framework, tier], outputs=[table])
    return tab


__all__ = ["build"]
