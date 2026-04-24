"""``DetectionAdapter`` protocol + attribute-shape assertion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - type-only
    from openpathai.detection.schema import DetectionResult

__all__ = ["DetectionAdapter"]


@runtime_checkable
class DetectionAdapter(Protocol):
    """Minimal surface every detector honours.

    Master-plan §11.6 narrowed for Phase 14: detection-only
    attributes + ``.build()`` + ``.detect()``.
    """

    id: str
    display_name: str
    gated: bool
    weight_source: str | None
    input_size: tuple[int, int]
    tier_compatibility: frozenset[str]
    vram_gb: float
    license: str
    citation: str

    def build(self, pretrained: bool = True) -> Any: ...

    def detect(
        self,
        image: Any,
        *,
        conf_threshold: float = 0.25,
    ) -> DetectionResult: ...


def _assert_detection_adapter_shape(adapter: DetectionAdapter) -> None:
    """Instance-level attribute + method sanity — paralleled to
    :func:`openpathai.foundation.adapter._assert_adapter_shape` so
    the error messages are clear when a new detector is missing
    something."""
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
    ):
        if not hasattr(adapter, attr):
            raise TypeError(
                f"{type(adapter).__name__!s} is missing the "
                f"required DetectionAdapter attribute {attr!r}"
            )
    for method in ("build", "detect"):
        if not callable(getattr(adapter, method, None)):
            raise TypeError(
                f"{type(adapter).__name__!s} is missing the "
                f"required DetectionAdapter method {method!r}"
            )
