"""Detection adapter registry + fallback resolver.

The resolver mirrors :mod:`openpathai.foundation.fallback` —
`resolve_detector(id)` returns a frozen ``FallbackDecision`` from
the foundation subpackage so downstream audit / manifest code can
treat detection and classification fallbacks uniformly.

Fallback chain:

1. The requested adapter. If ``build()`` succeeds → ``reason="ok"``.
2. On ``ImportError`` (AGPL guard — ultralytics missing):
   fall back to the YOLOv8 adapter, which then cascades…
3. …down to :class:`SyntheticDetector` — always loadable.

Strict mode (``allow_fallback=False``) re-raises as
:class:`GatedAccessError`, matching the Phase-13 contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from openpathai.detection.adapter import (
    DetectionAdapter,
    _assert_detection_adapter_shape,
)
from openpathai.detection.stubs import (
    RTDetrV2Stub,
    YOLOv11Stub,
    YOLOv26Stub,
)
from openpathai.detection.synthetic import SyntheticDetector
from openpathai.detection.yolo import YOLOv8Adapter
from openpathai.foundation.fallback import (
    FallbackDecision,
    GatedAccessError,
)

__all__ = [
    "DetectionRegistry",
    "default_detection_registry",
    "resolve_detector",
]


class DetectionRegistry:
    """Map detector id → adapter instance."""

    def __init__(self) -> None:
        self._adapters: dict[str, DetectionAdapter] = {}

    def register(self, adapter: DetectionAdapter) -> None:
        _assert_detection_adapter_shape(adapter)
        if adapter.id in self._adapters:
            raise ValueError(f"detection adapter id {adapter.id!r} is already registered")
        self._adapters[adapter.id] = adapter

    def get(self, adapter_id: str) -> DetectionAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(
                f"unknown detection adapter {adapter_id!r}; known: {sorted(self._adapters)}"
            ) from exc

    def has(self, adapter_id: str) -> bool:
        return adapter_id in self._adapters

    def names(self) -> list[str]:
        return sorted(self._adapters)

    def __iter__(self) -> Iterator[DetectionAdapter]:
        return iter(self._adapters[k] for k in sorted(self._adapters))

    def __len__(self) -> int:
        return len(self._adapters)


def default_detection_registry() -> DetectionRegistry:
    """Fresh registry with the Phase-14 adapters."""
    reg = DetectionRegistry()
    reg.register(cast(DetectionAdapter, YOLOv8Adapter()))
    reg.register(cast(DetectionAdapter, YOLOv11Stub()))
    reg.register(cast(DetectionAdapter, YOLOv26Stub()))
    reg.register(cast(DetectionAdapter, RTDetrV2Stub()))
    reg.register(cast(DetectionAdapter, SyntheticDetector()))
    return reg


_FALLBACK_ID = "synthetic_blob"


def resolve_detector(
    requested_id: str,
    *,
    registry: DetectionRegistry,
    allow_fallback: bool = True,
) -> FallbackDecision:
    """Resolve ``requested_id`` into an adapter actually loadable here.

    Returns a :class:`FallbackDecision` (re-used from
    :mod:`openpathai.foundation.fallback` for schema uniformity)
    whose ``resolved_id`` is either the request or a registered
    fallback.
    """
    try:
        adapter = registry.get(requested_id)
    except KeyError as exc:
        raise ValueError(
            f"unknown detection adapter {requested_id!r}; run "
            "`openpathai detection list` to see the registry."
        ) from exc

    # Synthetic + non-gated open adapters → just report ok.
    if not adapter.gated:
        return FallbackDecision(
            requested_id=requested_id,
            resolved_id=requested_id,
            reason="ok",
            message=f"{requested_id} is an open-access detector; no fallback needed.",
            hf_token_present=False,
        )

    # Try to build. Any failure routes to the synthetic fallback.
    try:
        adapter.build(pretrained=True)
    except ImportError as exc:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=_FALLBACK_ID,
            reason="import_error",
            message=(
                f"{requested_id} required an optional runtime "
                f"dependency that isn't installed: {exc!s}. Using "
                f"{_FALLBACK_ID} as fallback."
            ),
            hf_token_present=False,
        )
        if not allow_fallback:
            raise GatedAccessError(decision.message) from exc
        return decision
    except GatedAccessError as exc:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=_FALLBACK_ID,
            reason="hf_gated",
            message=(f"{requested_id} build failed ({exc!s}). Using {_FALLBACK_ID} as fallback."),
            hf_token_present=False,
        )
        if not allow_fallback:
            raise
        return decision
    except FileNotFoundError as exc:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=_FALLBACK_ID,
            reason="weight_file_missing",
            message=(
                f"{requested_id} weight file missing: {exc!s}. Using {_FALLBACK_ID} as fallback."
            ),
            hf_token_present=False,
        )
        if not allow_fallback:
            raise GatedAccessError(decision.message) from exc
        return decision

    return FallbackDecision(
        requested_id=requested_id,
        resolved_id=requested_id,
        reason="ok",
        message=f"{requested_id} loaded successfully.",
        hf_token_present=False,
    )
