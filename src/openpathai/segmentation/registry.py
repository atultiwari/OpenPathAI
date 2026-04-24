"""Segmentation registry — unified view of closed-vocab + promptable.

Like the detection registry, the fallback chain routes everything
to a license-clean synthetic segmenter when the requested adapter
can't be loaded.

Fallback targets:

* Closed-vocab adapter fails → :class:`SyntheticFullTissueSegmenter`
  (Otsu tissue/background).
* Promptable adapter fails → :class:`SyntheticClickSegmenter`
  (click → Otsu+connected-component flood-fill).

Strict mode re-raises as :class:`GatedAccessError`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from openpathai.foundation.fallback import (
    FallbackDecision,
    GatedAccessError,
)
from openpathai.segmentation.adapter import _assert_segmentation_adapter_shape
from openpathai.segmentation.promptable.sam import (
    MedSAM2PromptableStub,
    MedSAM3PromptableStub,
    MedSAMPromptableStub,
    SAM2PromptableStub,
)
from openpathai.segmentation.stubs import (
    AttentionUNetStub,
    HoverNetStub,
    NNUNetStub,
    SegFormerStub,
)
from openpathai.segmentation.synthetic import (
    SyntheticClickSegmenter,
    SyntheticFullTissueSegmenter,
)
from openpathai.segmentation.unet import TinyUNetAdapter

__all__ = [
    "CLOSED_FALLBACK_ID",
    "PROMPTABLE_FALLBACK_ID",
    "SegmentationRegistry",
    "default_segmentation_registry",
    "resolve_segmenter",
]


CLOSED_FALLBACK_ID = "synthetic_tissue"
PROMPTABLE_FALLBACK_ID = "synthetic_click"


class SegmentationRegistry:
    """Map segmenter id → adapter instance (closed or promptable)."""

    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}

    def register(self, adapter: Any) -> None:
        _assert_segmentation_adapter_shape(adapter)
        if adapter.id in self._adapters:
            raise ValueError(f"segmentation adapter id {adapter.id!r} is already registered")
        self._adapters[adapter.id] = adapter

    def get(self, adapter_id: str) -> Any:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(
                f"unknown segmentation adapter {adapter_id!r}; known: {sorted(self._adapters)}"
            ) from exc

    def has(self, adapter_id: str) -> bool:
        return adapter_id in self._adapters

    def names(self) -> list[str]:
        return sorted(self._adapters)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._adapters[k] for k in sorted(self._adapters))

    def __len__(self) -> int:
        return len(self._adapters)


def default_segmentation_registry() -> SegmentationRegistry:
    """Fresh registry with the Phase-14 adapters."""
    reg = SegmentationRegistry()
    reg.register(cast(Any, TinyUNetAdapter()))
    reg.register(cast(Any, AttentionUNetStub()))
    reg.register(cast(Any, NNUNetStub()))
    reg.register(cast(Any, SegFormerStub()))
    reg.register(cast(Any, HoverNetStub()))
    reg.register(cast(Any, SyntheticFullTissueSegmenter()))
    reg.register(cast(Any, SAM2PromptableStub()))
    reg.register(cast(Any, MedSAMPromptableStub()))
    reg.register(cast(Any, MedSAM2PromptableStub()))
    reg.register(cast(Any, MedSAM3PromptableStub()))
    reg.register(cast(Any, SyntheticClickSegmenter()))
    return reg


def resolve_segmenter(
    requested_id: str,
    *,
    registry: SegmentationRegistry,
    allow_fallback: bool = True,
) -> FallbackDecision:
    """Resolve ``requested_id`` into a registered segmenter actually
    loadable here. Routes to ``synthetic_tissue`` (closed-vocab) or
    ``synthetic_click`` (promptable) on failure."""
    try:
        adapter = registry.get(requested_id)
    except KeyError as exc:
        raise ValueError(
            f"unknown segmentation adapter {requested_id!r}; run "
            "`openpathai segmentation list` to see the registry."
        ) from exc

    fallback_id = PROMPTABLE_FALLBACK_ID if adapter.promptable else CLOSED_FALLBACK_ID

    if not adapter.gated:
        return FallbackDecision(
            requested_id=requested_id,
            resolved_id=requested_id,
            reason="ok",
            message=f"{requested_id} is open-access; no fallback needed.",
            hf_token_present=False,
        )

    try:
        adapter.build(pretrained=True)
    except ImportError as exc:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=fallback_id,
            reason="import_error",
            message=(
                f"{requested_id} required an optional dependency that "
                f"isn't installed: {exc!s}. Using {fallback_id} as fallback."
            ),
            hf_token_present=False,
        )
        if not allow_fallback:
            raise GatedAccessError(decision.message) from exc
        return decision
    except GatedAccessError as exc:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=fallback_id,
            reason="hf_gated",
            message=(f"{requested_id} build failed ({exc!s}). Using {fallback_id} as fallback."),
            hf_token_present=False,
        )
        if not allow_fallback:
            raise
        return decision
    except FileNotFoundError as exc:
        decision = FallbackDecision(
            requested_id=requested_id,
            resolved_id=fallback_id,
            reason="weight_file_missing",
            message=(
                f"{requested_id} weight file missing: {exc!s}. Using {fallback_id} as fallback."
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
