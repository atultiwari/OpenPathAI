"""Detection result schema — frozen pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BoundingBox",
    "DetectionResult",
]


class BoundingBox(BaseModel):
    """One axis-aligned detection in pixel coordinates.

    ``x`` / ``y`` are top-left. ``w`` / ``h`` are strictly positive.
    ``confidence`` sits in ``[0, 1]``. ``class_name`` is an opaque
    string — the adapter's model card resolves it to a human-friendly
    label downstream.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float = Field(ge=0.0)
    y: float = Field(ge=0.0)
    w: float = Field(gt=0.0)
    h: float = Field(gt=0.0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        """Convenience: return ``(x0, y0, x1, y1)`` for downstream
        viewers (OpenSeadragon in Phase 21)."""
        return (self.x, self.y, self.x + self.w, self.y + self.h)


class DetectionResult(BaseModel):
    """Output of one ``DetectionAdapter.detect`` call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    boxes: tuple[BoundingBox, ...]
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    model_id: str = Field(min_length=1)
    resolved_model_id: str = Field(min_length=1)

    def __len__(self) -> int:
        return len(self.boxes)

    def filter_by_confidence(self, threshold: float) -> DetectionResult:
        """Return a new result with boxes at or above ``threshold``."""
        return DetectionResult(
            boxes=tuple(b for b in self.boxes if b.confidence >= threshold),
            image_width=self.image_width,
            image_height=self.image_height,
            model_id=self.model_id,
            resolved_model_id=self.resolved_model_id,
        )
