"""Server configuration (Phase 19).

One pydantic model so the CLI, tests, and `create_app` factory all
agree on what is configurable. No environment-variable parsing in
route handlers — settings are injected at app construction time.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "DEFAULT_CORS_ORIGINS",
    "DEFAULT_PORT",
    "ServerSettings",
    "default_pipelines_dir",
    "generate_token",
]


DEFAULT_PORT: int = 7870
"""Default port. Chosen to sit next to Gradio (7860) without
clashing — both surfaces can run simultaneously during dev."""


DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)
"""Vite dev (5173) + preview (4173). Production deployments must
set ``cors_origins`` explicitly via env / CLI."""


def _default_home() -> Path:
    return Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))


def default_pipelines_dir() -> Path:
    """Where user-saved pipelines live. Returns the path without
    creating it — callers are responsible for ``mkdir``."""
    return _default_home() / "pipelines"


def generate_token() -> str:
    """Cryptographically random bearer token. Used as a fallback
    when neither ``--token`` nor ``OPENPATHAI_API_TOKEN`` is set."""
    return secrets.token_urlsafe(32)


class ServerSettings(BaseModel):
    """All knobs for the FastAPI app.

    Every field has a safe default so unit tests can construct a
    settings object with zero arguments. Real deployments override
    ``token`` + ``cors_origins`` at minimum.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = Field(default="127.0.0.1", min_length=1)
    """Loopback by default (iron rule #8 — keep traffic on-host)."""

    port: int = Field(default=DEFAULT_PORT, ge=1, le=65535)

    token: str = Field(default_factory=generate_token, min_length=16)
    """Bearer token. Clients must send ``Authorization: Bearer <token>``
    on every endpoint except ``/v1/health``."""

    cors_origins: tuple[str, ...] = Field(default=DEFAULT_CORS_ORIGINS)

    openpathai_home: Path = Field(default_factory=_default_home)
    """Root for pipelines, cache, audit DB, keys. Tests override
    to a tmp_path."""

    pipelines_dir: Path | None = Field(default=None)
    """Override for the pipelines directory. Defaults to
    ``openpathai_home/pipelines``."""

    max_concurrent_runs: int = Field(default=1, ge=1, le=16)
    """Phase 19 ships a small single-process executor. v2.5+ may
    swap in a distributed runner."""

    api_title: str = Field(default="OpenPathAI API", min_length=1)
    api_version: str = Field(default="v1", min_length=1)

    def resolved_pipelines_dir(self) -> Path:
        """Concrete pipelines directory — falls back to
        ``openpathai_home/pipelines``."""
        return self.pipelines_dir or (self.openpathai_home / "pipelines")
