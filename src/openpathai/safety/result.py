"""Typed outcome of a single analysis run.

Every classification + explainability pass — whether it started from the
CLI, the GUI, or a pipeline YAML — produces one :class:`AnalysisResult`.
This is the struct the PDF renderer reads, the GUI banner branches on,
and (from Phase 8 onwards) the audit DB persists. Keeping it frozen +
strongly-typed means the downstream views never have to second-guess
which fields are present.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from openpathai.safety.borderline import BorderlineDecision


def _utcnow() -> datetime:
    """Timezone-aware UTC ``now`` (``datetime.utcnow`` is deprecated in 3.12+)."""
    return datetime.now(UTC)


__all__ = [
    "AnalysisResult",
    "ClassProbability",
]


@dataclass(frozen=True, slots=True)
class ClassProbability:
    """A single ``(class_name, probability)`` pair."""

    class_name: str
    probability: float


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Everything a downstream surface (PDF, GUI, audit) needs about one run.

    Attributes
    ----------
    image_sha256:
        SHA-256 of the input image bytes. The PDF surfaces this instead
        of the original filesystem path so PHI never leaks into the
        artefact.
    image_caption:
        Optional human-supplied caption (shown in the PDF next to the
        thumbnail). Defaults to empty.
    model_name:
        Registered card name — e.g. ``"resnet18"``.
    explainer_name:
        Which explainer produced :attr:`overlay_png`.
    probabilities:
        One :class:`ClassProbability` per class. Order matches the
        classifier head output.
    borderline:
        :class:`BorderlineDecision` for the run.
    manifest_hash:
        SHA-256 of the run manifest JSON (empty string when the run was
        fired outside a manifest-producing pipeline — the GUI smoke path
        in Phase 6 / 7 falls into that bucket).
    overlay_png:
        Explainability overlay as raw PNG bytes. Rendered inline in the
        PDF.
    thumbnail_png:
        Input-tile PNG bytes (possibly downsampled). Rendered inline in
        the PDF.
    timestamp:
        When the run completed. Kept UTC-naive; injected in tests so PDF
        output is reproducible.
    """

    image_sha256: str
    model_name: str
    explainer_name: str
    probabilities: tuple[ClassProbability, ...]
    borderline: BorderlineDecision
    manifest_hash: str = ""
    overlay_png: bytes = b""
    thumbnail_png: bytes = b""
    image_caption: str = ""
    timestamp: datetime = field(default_factory=_utcnow)

    # ------------------------------------------------------------------
    # Convenience accessors — keep the PDF renderer / GUI callbacks terse.
    # ------------------------------------------------------------------

    @property
    def predicted_class_name(self) -> str:
        """Name of the class the borderline helper picked."""
        idx = self.borderline.predicted_class
        if idx < 0 or idx >= len(self.probabilities):
            return f"class_{idx}"
        return self.probabilities[idx].class_name

    @staticmethod
    def disclaimer() -> str:
        """Return the standard safety disclaimer used in PDFs + banners."""
        return (
            "OpenPathAI produces research-grade predictions and is NOT a "
            "medical device. Do not use this output as the sole basis for "
            "clinical decisions. Human expert review is required for any "
            "diagnostic or treatment decision."
        )
