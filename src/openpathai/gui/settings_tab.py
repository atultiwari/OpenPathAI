"""Settings tab — cache inspection, device default, version info."""

from __future__ import annotations

from typing import Any

from openpathai import __version__
from openpathai.gui.state import AppState
from openpathai.gui.views import cache_summary, device_choices
from openpathai.pipeline.cache import ContentAddressableCache


def build(state: AppState) -> Any:  # pragma: no cover - gradio-gated renderer
    import gradio as gr

    with gr.Blocks() as tab:
        gr.Markdown(f"### OpenPathAI v{__version__}")

        with gr.Row():
            gr.Textbox(
                label="Cache root",
                value=str(state.cache_root),
                interactive=False,
            )
            device = gr.Dropdown(
                device_choices(),
                value=state.device,
                label="Default device",
            )

        summary_box = gr.JSON(value=cache_summary(state.cache_root), label="Cache summary")
        refresh = gr.Button("Refresh")

        def _refresh() -> dict[str, str]:
            return cache_summary(state.cache_root)

        refresh.click(_refresh, outputs=[summary_box])

        clear_btn = gr.Button("Clear cache", variant="stop")
        status = gr.Markdown("")

        def _clear() -> tuple[str, dict[str, str]]:
            cache = ContentAddressableCache(root=state.cache_root)
            removed = cache.clear()
            return (
                f"Removed **{removed}** cache entr{'y' if removed == 1 else 'ies'}.",
                cache_summary(state.cache_root),
            )

        clear_btn.click(_clear, outputs=[status, summary_box])
        gr.Markdown(
            "Documentation: "
            "[atultiwari.github.io/OpenPathAI](https://atultiwari.github.io/OpenPathAI/)."
        )
        # Surface the "default device" selection so future tabs can
        # read it via the shared ``state`` object. Phase 6 is read-only
        # on this front; Phase 10 wires live persistence.
        _ = device
    return tab


__all__ = ["build"]
