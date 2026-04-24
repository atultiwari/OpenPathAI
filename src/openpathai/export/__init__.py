"""Export surface — Colab notebook generator (Phase 11).

Public API:

* :func:`render_notebook` — build a Colab-ready ipynb dict.
* :func:`write_notebook` — thin wrapper that writes it to disk.
* :class:`ColabExportError` — raised on invalid inputs.

The template lives at ``openpathai/export/templates/colab.ipynb.j2``.
Jinja2 is imported lazily inside :func:`render_notebook` so
``import openpathai.export`` stays cheap when users only want
``openpathai sync`` (the round-trip import helper in
:mod:`openpathai.safety.audit.sync`).
"""

from __future__ import annotations

from openpathai.export.colab import (
    ColabExportError,
    render_notebook,
    write_notebook,
)

__all__ = [
    "ColabExportError",
    "render_notebook",
    "write_notebook",
]
