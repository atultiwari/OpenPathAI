"""Tests that require gradio — gated behind ``pytest.importorskip``."""

from __future__ import annotations

import importlib.util
import sys

import pytest

from openpathai.gui.app import TAB_ORDER

gradio_missing = importlib.util.find_spec("gradio") is None


def test_tab_order_matches_docs() -> None:
    assert TAB_ORDER == (
        "Analyse",
        "Train",
        "Datasets",
        "Models",
        "Settings",
    )


def test_importing_openpathai_gui_does_not_load_gradio() -> None:
    # Fresh import: if the package accidentally eagerly loaded gradio
    # at module level, it would show up in sys.modules even when
    # gradio wasn't installed (no-op if gradio is absent).
    sys.modules.pop("gradio", None)
    for mod in list(sys.modules):
        if mod.startswith("openpathai.gui"):
            sys.modules.pop(mod, None)

    # Re-import the package entry point.
    import openpathai.gui  # noqa: F401

    assert "gradio" not in sys.modules, (
        "openpathai.gui must not eagerly import gradio — keep imports " "inside function bodies."
    )


def test_tab_modules_import_without_gradio() -> None:
    """Every tab module must be importable without gradio so coverage
    reflects the torch-free surface accurately. Gradio is only required
    inside each ``build(state)`` function body."""
    import importlib

    for name in (
        "analyse_tab",
        "datasets_tab",
        "models_tab",
        "settings_tab",
        "train_tab",
    ):
        module = importlib.import_module(f"openpathai.gui.{name}")
        assert hasattr(module, "build")


@pytest.mark.skipif(gradio_missing, reason="gradio not installed")
def test_build_app_returns_blocks() -> None:
    import gradio as gr

    from openpathai import AppState
    from openpathai.gui.app import build_app

    app = build_app(AppState())
    assert isinstance(app, gr.Blocks)
