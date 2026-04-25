"""Bearer-token authentication dependency (Phase 19).

One shared token per deployment. Clients send ``Authorization:
Bearer <token>`` on every endpoint except ``/v1/health``. We use
``secrets.compare_digest`` so a wrong token cannot be timing-
attacked character by character.

This is deliberately the simplest thing that could possibly work.
Multi-user / RBAC / OIDC are v2.5+ concerns.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from fastapi import Depends, Header, HTTPException, Request, status

if TYPE_CHECKING:  # pragma: no cover - type-only
    from openpathai.server.config import ServerSettings

__all__ = [
    "AUTH_SCHEME",
    "require_token",
]


AUTH_SCHEME: str = "Bearer"


def _extract_bearer(header_value: str | None) -> str | None:
    if not header_value:
        return None
    parts = header_value.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != AUTH_SCHEME.lower():
        return None
    return token.strip() or None


def require_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Dependency: 401 unless the caller presents the configured bearer.

    The settings live on ``request.app.state.settings`` (populated
    by :func:`openpathai.server.app.create_app`).

    Phase 21 also accepts ``?token=<bearer>`` as a fallback. The
    OpenSeadragon viewer drives DZI XML + tile PNG fetches that don't
    always carry custom headers (e.g. some proxy paths strip them);
    a query-string token is the canonical pattern for auth-gated
    tile servers and keeps the viewer working in every browser /
    proxy combo. The query token is opt-in and the bearer header
    still wins when present.
    """
    settings: ServerSettings | None = getattr(request.app.state, "settings", None)
    if settings is None:  # pragma: no cover - defensive; app always sets this
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="server settings not initialised",
        )
    token = _extract_bearer(authorization)
    if token is None:
        # Fallback: ``?token=<bearer>`` on the URL.
        query_token = request.query_params.get("token")
        if query_token:
            token = query_token.strip() or None
    if token is None or not secrets.compare_digest(token, settings.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid bearer token",
            headers={"WWW-Authenticate": AUTH_SCHEME},
        )


AuthDependency = Depends(require_token)
