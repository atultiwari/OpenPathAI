"""Tests that require gradio — gated behind ``pytest.importorskip``."""

from __future__ import annotations

import importlib.util
import sys

import pytest

from openpathai.gui.app import TAB_ORDER


def _gradio_is_usable() -> bool:
    """Return ``True`` iff gradio is importable *and* not a stale
    namespace-package stub left behind by ``uv sync`` swapping extras.
    """
    spec = importlib.util.find_spec("gradio")
    if spec is None or spec.origin is None:
        return False
    # A partial install leaves ``gradio.blocks`` unavailable.
    return importlib.util.find_spec("gradio.blocks") is not None


gradio_missing = not _gradio_is_usable()


def test_tab_order_matches_docs() -> None:
    assert TAB_ORDER == (
        "Analyse",
        "Datasets",
        "Train",
        "Models",
        "Runs",
        "Cohorts",
        "Settings",
    )


def test_importing_openpathai_gui_does_not_load_gradio() -> None:
    # Fresh import: if the package accidentally eagerly loaded gradio
    # at module level, it would show up in sys.modules even when
    # gradio wasn't installed (no-op if gradio is absent).
    for mod in [m for m in sys.modules if m == "gradio" or m.startswith("gradio.")]:
        sys.modules.pop(mod, None)
    for mod in [m for m in sys.modules if m.startswith("openpathai.gui")]:
        sys.modules.pop(mod, None)

    # Re-import the package entry point.
    import openpathai.gui  # noqa: F401

    loaded_gradio = [m for m in sys.modules if m == "gradio" or m.startswith("gradio.")]
    assert not loaded_gradio, (
        "openpathai.gui must not eagerly import gradio — keep imports "
        f"inside function bodies. Loaded: {loaded_gradio!r}"
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
