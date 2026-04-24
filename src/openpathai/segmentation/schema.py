"""Segmentation result schema — ``Mask`` + ``SegmentationResult``.

``Mask`` wraps a ``(H, W)`` integer label map plus the ordered
class-name tuple. The underlying numpy array is immutable (we
``.setflags(write=False)`` at construction) so downstream
consumers can trust it.
"""

from __future__ import annotations

from types import MappingProxyType

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Mask",
    "SegmentationResult",
]


class Mask(BaseModel):
    """``(H, W)`` integer label map + ordered class-name tuple.

    Class id 0 is conventionally "background". ``class_names[i]``
    is the label for mask value ``i``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    array: np.ndarray
    class_names: tuple[str, ...]

    def model_post_init(self, __context: object) -> None:
        # Enforce shape + dtype invariants once at construction.
        if self.array.ndim != 2:
            raise ValueError(f"Mask.array must be 2-D (H, W); got shape {self.array.shape}")
        if self.array.dtype.kind not in {"i", "u"}:
            raise ValueError(f"Mask.array must be integer dtype; got {self.array.dtype}")
        if not self.class_names:
            raise ValueError("Mask.class_names must be non-empty")
        max_label = int(self.array.max()) if self.array.size else 0
        if max_label >= len(self.class_names):
            raise ValueError(
                f"Mask max label {max_label} >= len(class_names) {len(self.class_names)}"
            )
        # Freeze the array in place so downstream consumers can
        # assume immutability. ``object.__setattr__`` sidesteps the
        # pydantic frozen=True guard on our own internal state.
        self.array.setflags(write=False)

    @property
    def shape(self) -> tuple[int, int]:
        return (int(self.array.shape[0]), int(self.array.shape[1]))

    def class_id(self, name: str) -> int:
        try:
            return self.class_names.index(name)
        except ValueError as exc:
            raise ValueError(f"{name!r} not in class_names {self.class_names!r}") from exc


class SegmentationResult(BaseModel):
    """Output of ``.segment()`` / ``.segment_with_prompt()``.

    ``metadata`` is read-only: ``frozen=True`` blocks re-assignment at
    the model level, and :meth:`model_post_init` wraps the dict in
    :class:`types.MappingProxyType` so in-place mutation
    (``result.metadata["x"] = 1``) raises ``TypeError`` too. Callers
    that need to carry enriched metadata downstream should ``dict(...)``
    a copy before mutating.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mask: Mask
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    model_id: str = Field(min_length=1)
    resolved_model_id: str = Field(min_length=1)
    metadata: dict[str, float | int | str | bool] = Field(default_factory=dict)

    def model_post_init(self, __context: object) -> None:
        # Swap the mutable dict for a read-only view. We use
        # ``object.__setattr__`` to bypass the pydantic frozen guard on
        # our own internal state — same pattern as ``Mask.array``.
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
