"""OpenPathAI FastAPI backend (Phase 19) — first of three phases
that together ship the v2.0 React canvas.

The server wraps the v1 library surface — node catalog, model +
dataset registries, pipeline CRUD, async run execution, audit-log
reads, and the NL primitives — as a versioned ``/v1`` JSON API.
Phase 20 adds the React canvas; Phase 21 adds the OpenSeadragon
viewer + run-audit modal.

Every route is a thin shell over a library call (iron rule #1) and
every response body is PHI-redacted at the serialisation boundary
(iron rule #8).

Importing this module **does not** pull ``fastapi`` or ``uvicorn``
— both are lazy-loaded from ``app.create_app()`` so the core
``openpathai`` install stays small.
"""

from __future__ import annotations

from openpathai.server.config import ServerSettings

__all__ = ["ServerSettings", "create_app"]


def create_app(settings: ServerSettings | None = None):
    """Factory for the FastAPI application. Imported lazily so the
    ``openpathai`` library does not pay the fastapi import cost."""
    from openpathai.server.app import create_app as _create_app

    return _create_app(settings)
