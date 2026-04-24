"""SegmentationAdapter + PromptableSegmentationAdapter protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - type-only
    from openpathai.segmentation.schema import SegmentationResult

__all__ = [
    "PromptableSegmentationAdapter",
    "SegmentationAdapter",
]


@runtime_checkable
class SegmentationAdapter(Protocol):
    """Closed-vocabulary segmenter — fixed class list at build time."""

    id: str
    display_name: str
    gated: bool
    weight_source: str | None
    input_size: tuple[int, int]
    num_classes: int
    class_names: tuple[str, ...]
    tier_compatibility: frozenset[str]
    vram_gb: float
    license: str
    citation: str
    promptable: bool  # False

    def build(self, pretrained: bool = True) -> Any: ...
    def segment(self, image: Any) -> SegmentationResult: ...


@runtime_checkable
class PromptableSegmentationAdapter(Protocol):
    """Promptable segmenter — class list replaced by prompt inputs."""

    id: str
    display_name: str
    gated: bool
    weight_source: str | None
    input_size: tuple[int, int]
    tier_compatibility: frozenset[str]
    vram_gb: float
    license: str
    citation: str
    promptable: bool  # True

    def build(self, pretrained: bool = True) -> Any: ...
    def segment_with_prompt(
        self,
        image: Any,
        *,
        point: tuple[int, int] | None = None,
        box: tuple[int, int, int, int] | None = None,
    ) -> SegmentationResult: ...


def _assert_segmentation_adapter_shape(adapter: Any) -> None:
    """Attribute + method sanity check. Works for both closed-vocab
    and promptable adapters — the differentiator is ``.promptable``."""
    for attr in (
        "id",
        "display_name",
        "gated",
        "weight_source",
        "input_size",
        "tier_compatibility",
        "vram_gb",
        "license",
        "citation",
        "promptable",
    ):
        if not hasattr(adapter, attr):
            raise TypeError(
                f"{type(adapter).__name__!s} is missing the required "
                f"segmentation attribute {attr!r}"
            )
    if not callable(getattr(adapter, "build", None)):
        raise TypeError(f"{type(adapter).__name__!s} is missing `build`")
    if adapter.promptable:
        if not callable(getattr(adapter, "segment_with_prompt", None)):
            raise TypeError(
                f"{type(adapter).__name__!s} is promptable but lacks `segment_with_prompt`"
            )
    else:
        for attr in ("num_classes", "class_names"):
            if not hasattr(adapter, attr):
                raise TypeError(f"{type(adapter).__name__!s} is closed-vocab but lacks {attr!r}")
        if not callable(getattr(adapter, "segment", None)):
            raise TypeError(f"{type(adapter).__name__!s} is closed-vocab but lacks `segment`")
