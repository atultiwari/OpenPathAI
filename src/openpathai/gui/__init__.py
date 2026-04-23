"""Gradio GUI — Analyse / Train / Datasets / Models / Settings.

Phase 6 adds the pathologist-facing surface. Every gradio import is
deferred to function bodies so ``import openpathai.gui`` does not
trigger the ~200 MB gradio dependency chain at module load time —
keeping ``openpathai --help`` fast and the core test matrix torch-
free.

Public API:

* :func:`build_app` — returns the top-level ``gradio.Blocks``.
* :func:`launch_app` — build + ``.launch()`` in one call.
* :class:`AppState` — immutable view-model state dataclass.
* :func:`datasets_rows`, :func:`models_rows`, :func:`cache_summary` —
  pure-python view helpers shared by the tab modules (and unit tests).
"""

from __future__ import annotations

from openpathai.gui.app import TAB_ORDER, build_app, launch_app
from openpathai.gui.state import AppState
from openpathai.gui.views import (
    cache_summary,
    datasets_rows,
    device_choices,
    explainer_choices,
    models_rows,
    target_layer_hint,
)

__all__ = [
    "TAB_ORDER",
    "AppState",
    "build_app",
    "cache_summary",
    "datasets_rows",
    "device_choices",
    "explainer_choices",
    "launch_app",
    "models_rows",
    "target_layer_hint",
]
