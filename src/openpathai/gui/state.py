"""Session state for the Gradio GUI.

Pure Python — no gradio dependency. ``AppState`` is a frozen dataclass
so updates go through a ``copy(update={...})``-style helper, matching
the "never mutate, always return a new object" rule from the iron
rules (``CLAUDE.md`` §2, immutability).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from openpathai.pipeline.cache import default_cache_root

__all__ = ["AppState"]


@dataclass(frozen=True)
class AppState:
    """Immutable view-model state for the GUI.

    Fields are the union of "what the user picked last" plus "shared
    knobs the whole app reads from." Every callback returns a new
    ``AppState`` via :meth:`updated` rather than mutating in place.
    """

    cache_root: Path = field(default_factory=default_cache_root)
    device: str = "auto"
    selected_model: str | None = None
    selected_dataset: str | None = None
    selected_explainer: str = "gradcam"
    share: bool = False
    host: str = "127.0.0.1"
    port: int = 7860

    def updated(self, **changes: object) -> AppState:
        """Return a copy of ``self`` with selected fields overridden."""
        return replace(self, **changes)  # type: ignore[arg-type]

    def with_cache_root(self, path: str | Path) -> AppState:
        return self.updated(cache_root=Path(path))
