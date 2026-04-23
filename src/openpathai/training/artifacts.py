"""Pipeline artifacts produced by the Phase 3 training engine."""

from __future__ import annotations

from pydantic import Field

from openpathai.pipeline.schema import Artifact

__all__ = [
    "EpochRecord",
    "TrainingReportArtifact",
]


class EpochRecord(Artifact):
    """One epoch's metrics."""

    epoch: int
    train_loss: float
    val_loss: float | None = None
    val_accuracy: float | None = None
    val_macro_f1: float | None = None
    val_ece: float | None = None


class TrainingReportArtifact(Artifact):
    """End-of-run training report.

    Everything here round-trips through JSON and is safe to drop into
    the run manifest. Non-JSON-friendly fields (state dicts, calibration
    plots) are written next to the checkpoint on disk and referenced by
    path.
    """

    model_card: str
    num_classes: int
    epochs: int
    seed: int
    device: str
    checkpoint_path: str | None = None
    final_train_loss: float
    final_val_loss: float | None = None
    final_val_accuracy: float | None = None
    final_val_macro_f1: float | None = None
    ece_before_calibration: float | None = None
    ece_after_calibration: float | None = None
    temperature: float | None = None
    class_names: tuple[str, ...] = Field(default_factory=tuple)
    history: tuple[EpochRecord, ...] = Field(default_factory=tuple)
