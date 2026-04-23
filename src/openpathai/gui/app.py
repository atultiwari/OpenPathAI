"""Root Gradio app — five tabs wired onto a single Blocks surface.

Gradio is lazy-imported inside :func:`build_app` so ``import openpathai``
and ``openpathai --help`` stay fast. Every tab module exposes a
``build(state)`` function that returns a ``gradio.Blocks`` and
registers its own event handlers.

The business logic never lives here: every callback in the tab
modules delegates to a function already shipped in
``openpathai.{training, explain, data, pipeline}``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openpathai.gui.state import AppState

if TYPE_CHECKING:  # pragma: no cover - type hints only
    import gradio as gr

__all__ = [
    "TAB_ORDER",
    "build_app",
    "launch_app",
]


TAB_ORDER: tuple[str, ...] = (
    "Analyse",
    "Train",
    "Datasets",
    "Models",
    "Settings",
)


def _require_gradio() -> Any:  # pragma: no cover - trivially wraps the import
    try:
        import gradio as gr
    except ImportError as exc:
        raise ImportError(
            "The Gradio GUI requires the `[gui]` extra. Install via `uv sync --extra gui`."
        ) from exc
    return gr


def build_app(state: AppState | None = None) -> gr.Blocks:  # pragma: no cover - gradio
    """Assemble the five-tab OpenPathAI app.

    Returns the ``gradio.Blocks`` instance without calling ``.launch()``
    so tests (and the CLI) can decide how to host it.
    """
    gr = _require_gradio()

    from openpathai.gui import (
        analyse_tab,
        datasets_tab,
        models_tab,
        settings_tab,
        train_tab,
    )

    state = state if state is not None else AppState()

    with gr.Blocks(title="OpenPathAI", theme=gr.themes.Soft()) as app:
        gr.Markdown("# OpenPathAI")
        gr.Markdown(
            "Open-source, reproducible, compute-tier-aware workflow "
            "environment for computational pathology. "
            "[Docs](https://atultiwari.github.io/OpenPathAI/)."
        )
        with gr.Tabs():
            with gr.Tab("Analyse"):
                analyse_tab.build(state)
            with gr.Tab("Train"):
                train_tab.build(state)
            with gr.Tab("Datasets"):
                datasets_tab.build(state)
            with gr.Tab("Models"):
                models_tab.build(state)
            with gr.Tab("Settings"):
                settings_tab.build(state)
    return app


def launch_app(
    state: AppState | None = None,
    *,
    host: str | None = None,
    port: int | None = None,
    share: bool | None = None,
    **launch_kwargs: Any,
) -> None:  # pragma: no cover - network launch
    """Build + launch the GUI.

    Defaults come from :class:`AppState`. Tests never call this — they
    verify the rendered Blocks object via :func:`build_app`.
    """
    effective_state = state if state is not None else AppState()
    app = build_app(effective_state)
    # ``show_api=False`` skips the Gradio JS-client schema introspection
    # step, which tripped on older gradio-client versions when pydantic
    # inputs surfaced boolean JSON-schema values. The tabs do not rely
    # on the JS-client autogen, so disabling it is a no-op for users.
    launch_kwargs.setdefault("show_api", False)
    app.launch(
        server_name=host or effective_state.host,
        server_port=port if port is not None else effective_state.port,
        share=share if share is not None else effective_state.share,
        **launch_kwargs,
    )
