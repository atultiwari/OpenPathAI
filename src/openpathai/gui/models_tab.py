"""Models tab — filter + inspect every registered model card.

Phase 7 adds a **status + issues** column so cards that fail the
safety-v1 contract render with their failure codes. The Analyse and
Train pickers continue to consume :meth:`ModelRegistry.names` which
already excludes failing cards, so a contract violation never lets an
incomplete card reach a classifier.
"""

from __future__ import annotations

from typing import Any

from openpathai.gui.views import models_rows

MODELS_HEADERS = [
    "name",
    "display_name",
    "family",
    "framework",
    "params_m",
    "input_size",
    "license",
    "gated",
    "status",
    "issues",
]


def _rows_as_list(  # pragma: no cover - gradio
    *,
    family: str | None = None,
    framework: str | None = None,
    tier: str | None = None,
) -> list[list[str]]:
    rows = models_rows(family=family, framework=framework, tier=tier)
    if not rows:
        return []
    return [[row[key] for key in MODELS_HEADERS] for row in rows]


def build(state: Any) -> Any:  # pragma: no cover - gradio-gated renderer
    import gradio as gr

    del state
    with gr.Blocks() as tab:
        gr.Markdown(
            "### Model registry (Tier A)\n"
            "Cards are listed alphabetically. Rows with `status=incomplete` "
            "fail the Phase 7 safety-v1 contract and are **excluded** from "
            "the Analyse / Train pickers until the corresponding YAML is "
            "updated; the `issues` column names the missing fields."
        )
        with gr.Row():
            family = gr.Textbox(label="Family filter (resnet, vit, ...)", value="")
            framework = gr.Textbox(label="Framework filter", value="")
            tier = gr.Dropdown(["", "T1", "T2", "T3"], value="", label="Tier filter")
        refresh = gr.Button("Refresh")
        table = gr.Dataframe(
            headers=MODELS_HEADERS,
            value=_rows_as_list(),
            interactive=False,
        )

        def _filter(fam: str, fw: str, tier_opt: str) -> list[list[str]]:
            return _rows_as_list(
                family=fam or None,
                framework=fw or None,
                tier=tier_opt or None,
            )

        refresh.click(_filter, inputs=[family, framework, tier], outputs=[table])
    return tab


__all__ = ["MODELS_HEADERS", "build"]
