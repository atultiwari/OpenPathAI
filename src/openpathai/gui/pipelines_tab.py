"""Pipelines tab — list shipped YAMLs + MedGemma-draft accordion.

Phase 16 deliverable. The "Describe what you want" chat accordion
wraps :func:`openpathai.gui.views.nl_draft_pipeline_for_gui`
which in turn wraps the Phase-15 :func:`draft_pipeline_from_prompt`
with fallback-messaging for missing LLM backends.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpathai.gui.views import nl_draft_pipeline_for_gui

__all__ = ["build"]


def _list_shipped_pipelines() -> list[dict[str, str]]:
    """Return one row per ``pipelines/*.yaml`` on disk."""
    root = Path(__file__).resolve().parents[3] / "pipelines"
    if not root.is_dir():
        return []
    rows: list[dict[str, str]] = []
    for path in sorted(root.glob("*.yaml")):
        rows.append(
            {
                "name": path.stem,
                "path": str(path.relative_to(root.parent)),
                "size_kb": f"{path.stat().st_size / 1024:.1f}",
            }
        )
    return rows


def build(state: Any) -> None:  # pragma: no cover - gradio
    import gradio as gr

    del state  # unused — this tab is stateless.

    with gr.Column():
        gr.Markdown("## Pipelines — shipped YAMLs + draft from a prompt")

        with gr.Row():
            refresh_btn = gr.Button("Refresh list")

        pipelines_df = gr.Dataframe(
            headers=["name", "path", "size_kb"],
            value=[[r["name"], r["path"], r["size_kb"]] for r in _list_shipped_pipelines()],
            interactive=False,
            label="Shipped pipelines",
        )

        def _refresh() -> list[list[str]]:
            return [[r["name"], r["path"], r["size_kb"]] for r in _list_shipped_pipelines()]

        refresh_btn.click(_refresh, outputs=[pipelines_df])

        with gr.Accordion("Describe what you want (MedGemma draft)", open=False):
            gr.Markdown(
                "Ask the local LLM to draft a pipeline YAML. Iron rule "
                "#9: the draft is **never** auto-executed — review the "
                "YAML, then run it explicitly via `openpathai run` or "
                "the Train tab."
            )
            prompt_box = gr.Textbox(
                label="Prompt",
                placeholder="fine-tune resnet18 on lc25000 for 2 epochs",
            )
            draft_btn = gr.Button("Draft", variant="primary")
            draft_yaml = gr.Code(label="Drafted YAML", language="yaml")
            draft_meta = gr.JSON(label="Draft metadata")
            draft_err = gr.Markdown("")

            def _draft(p: str) -> tuple[str, dict, str]:
                result = nl_draft_pipeline_for_gui(p)
                if "error" in result:
                    return "", {}, f"**Draft failed:** {result['error']}"
                return (
                    str(result.get("yaml_text", "")),
                    {k: v for k, v in result.items() if k != "yaml_text"},
                    "",
                )

            draft_btn.click(
                _draft,
                inputs=[prompt_box],
                outputs=[draft_yaml, draft_meta, draft_err],
            )
