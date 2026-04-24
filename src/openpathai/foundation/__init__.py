"""OpenPathAI — foundation backbones + gated-access fallback (Phase 13).

Library surface (all pure-numpy / torch-optional):

* :class:`FoundationAdapter` — embedding-focused protocol every
  foundation backbone conforms to.
* :class:`FallbackDecision` — what :func:`resolve_backbone` returned,
  including ``requested_id`` vs ``resolved_id`` and a banner message
  that Phase 16 can render in the GUI.
* :class:`GatedAccessError` — raised when a gated model cannot be
  loaded and the caller explicitly requested no-fallback.
* :class:`FoundationRegistry` — maps adapter id → adapter class;
  :func:`default_foundation_registry` loads the eight shipped
  adapters (DINOv2 / UNI / CTransPath + 5 stubs).
"""

from __future__ import annotations

from openpathai.foundation.adapter import FoundationAdapter
from openpathai.foundation.fallback import (
    FallbackDecision,
    FallbackReason,
    GatedAccessError,
    build_resolved_adapter,
    resolve_backbone,
    resolve_backbone_and_build,
)
from openpathai.foundation.registry import (
    FoundationRegistry,
    default_foundation_registry,
)

__all__ = [
    "FallbackDecision",
    "FallbackReason",
    "FoundationAdapter",
    "FoundationRegistry",
    "GatedAccessError",
    "build_resolved_adapter",
    "default_foundation_registry",
    "resolve_backbone",
    "resolve_backbone_and_build",
]
