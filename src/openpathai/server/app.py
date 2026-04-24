"""FastAPI application factory (Phase 19).

One factory so tests and the ``openpathai serve`` CLI construct
the app the same way. Sub-routers are mounted under ``/v1`` and
every route attaches the :func:`openpathai.server.auth.require_token`
dependency except the public health check.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from openpathai.server.config import ServerSettings
from openpathai.server.phi import redact_response_payload
from openpathai.server.schemas import ErrorResponse

if TYPE_CHECKING:  # pragma: no cover - type-only
    from starlette.types import ASGIApp

__all__ = ["create_app"]


def create_app(settings: ServerSettings | None = None) -> FastAPI:
    """Build a fresh FastAPI app bound to ``settings``.

    Callers that want isolation between tests must call this factory
    each time — there is no global singleton.
    """
    settings = settings or ServerSettings()

    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description=(
            "OpenPathAI backend (Phase 19). Exposes the v1 library surface "
            "— node catalog, model + dataset registries, pipeline CRUD, "
            "async run execution, audit-log reads, NL primitives — as a "
            "versioned /v1 JSON API ready for the Phase-20 React canvas."
        ),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        del request
        body = ErrorResponse(
            detail=str(exc.detail) if exc.detail is not None else "",
            code=f"http_{exc.status_code}",
        ).model_dump(mode="json")
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        errors = exc.errors()
        field_errors = [jsonable_encoder(err) for err in errors]
        body = ErrorResponse(
            detail="request validation failed",
            code="validation_error",
            field_errors=field_errors,
        ).model_dump(mode="json")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=body,
        )

    @app.middleware("http")
    async def _phi_redaction_middleware(request: Request, call_next):
        response = await call_next(request)
        # Only rewrite JSON response bodies. File / stream responses
        # pass through unchanged.
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return response
        body_chunks: list[bytes] = []
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body_chunks.append(chunk)
        raw = b"".join(body_chunks)
        if not raw:
            return JSONResponse(
                content=None,
                status_code=response.status_code,
                headers=_preserve_headers(dict(response.headers)),
            )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:  # pragma: no cover - non-JSON claiming JSON ct
            return JSONResponse(
                content=raw.decode("utf-8", errors="replace"),
                status_code=response.status_code,
                headers=_preserve_headers(dict(response.headers)),
            )
        redacted = redact_response_payload(payload)
        return JSONResponse(
            content=redacted,
            status_code=response.status_code,
            headers=_preserve_headers(dict(response.headers)),
        )

    # Mount sub-routers. Each router is imported lazily inside the
    # factory so a caller that just wants ``ServerSettings`` (e.g. a
    # unit test) does not pay the full fastapi+uvicorn import cost.
    from openpathai.server.routes import (
        audit,
        datasets,
        health,
        manifest,
        models,
        nl,
        nodes,
        pipelines,
        runs,
    )

    # Public.
    app.include_router(health.router, prefix="/v1")
    # Auth-gated.
    app.include_router(nodes.router, prefix="/v1")
    app.include_router(models.router, prefix="/v1")
    app.include_router(datasets.router, prefix="/v1")
    app.include_router(pipelines.router, prefix="/v1")
    app.include_router(runs.router, prefix="/v1")
    app.include_router(audit.router, prefix="/v1")
    app.include_router(nl.router, prefix="/v1")
    app.include_router(manifest.router, prefix="/v1")

    return app


_SKIP_HEADERS = frozenset({"content-length", "content-encoding", "transfer-encoding"})


def _preserve_headers(headers: dict[str, str]) -> dict[str, str]:
    """Strip headers that FastAPI will recompute when we replace the body."""
    return {k: v for k, v in headers.items() if k.lower() not in _SKIP_HEADERS}


def mount(app: ASGIApp | None = None) -> FastAPI:  # pragma: no cover - convenience
    """Helper for mounting the app inside a larger ASGI stack.

    Currently just forwards to :func:`create_app`. Reserved for a
    future Phase 20 that wires React's Vite build dir under ``/``.
    """
    del app
    return create_app()
