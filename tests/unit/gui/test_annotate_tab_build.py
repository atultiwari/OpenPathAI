"""Phase 16 — Annotate + Pipelines tab build smoke."""

from __future__ import annotations

import pytest

gr = pytest.importorskip("gradio")

from openpathai.gui.state import AppState  # noqa: E402


def test_annotate_tab_build_returns_gradio_component() -> None:
    from openpathai.gui import annotate_tab

    with gr.Blocks() as demo:
        annotate_tab.build(AppState())
    assert isinstance(demo, gr.Blocks)


def test_pipelines_tab_build_returns_gradio_component() -> None:
    from openpathai.gui import pipelines_tab

    with gr.Blocks() as demo:
        pipelines_tab.build(AppState())
    assert isinstance(demo, gr.Blocks)


def test_build_app_produces_expected_tab_order() -> None:
    """Phase 16 tab order contract — nine tabs in the fixed order."""
    from openpathai.gui.app import build_app

    demo = build_app()
    # Gradio 5 exposes the tab list via demo.blocks; walk and collect
    # the tab labels.
    labels: list[str] = []
    for block in demo.blocks.values():
        if type(block).__name__ == "Tab":
            label = getattr(block, "label", None)
            if isinstance(label, str):
                labels.append(label)
    # The assertion is on order + membership; label reads are stable
    # across Gradio 5 minor versions.
    expected = [
        "Analyse",
        "Pipelines",
        "Datasets",
        "Train",
        "Models",
        "Runs",
        "Cohorts",
        "Annotate",
        "Settings",
    ]
    assert labels == expected, f"got {labels!r}"
