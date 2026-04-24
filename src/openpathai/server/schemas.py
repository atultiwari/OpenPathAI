"""Shared response models for the Phase-19 FastAPI backend.

Every route returns a pydantic model, never a raw dict. This gives
us an OpenAPI schema for free + a place to hang iron-rule-#8 PHI
redaction as a ``model_validator``.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ErrorResponse",
    "HealthResponse",
    "PagedResponse",
    "VersionResponse",
]


_T = TypeVar("_T")


class HealthResponse(BaseModel):
    """``GET /v1/health`` — liveness probe; no auth."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = Field(default="ok")
    api_version: str


class VersionResponse(BaseModel):
    """``GET /v1/version`` — reports the installed ``openpathai``
    library version + API version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    openpathai_version: str
    api_version: str
    commit: str | None = None


class ErrorResponse(BaseModel):
    """Consistent error envelope for 4xx / 5xx responses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    detail: str
    code: str | None = None
    field_errors: list[dict[str, Any]] | None = None


class PagedResponse(BaseModel, Generic[_T]):
    """Generic paginated list response.

    ``total`` is the count after filtering; ``items`` holds the
    requested slice. Callers never assume pagination beyond what
    this envelope advertises.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[_T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
