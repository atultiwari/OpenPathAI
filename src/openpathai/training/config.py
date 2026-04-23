"""Typed configuration for the Phase 3 training engine.

Every training run is fully described by a :class:`TrainingConfig`
instance; the :class:`openpathai.training.node.train` node accepts it as
its pydantic input so the pipeline cache keys pick up every knob that
affects the trained weights.

No torch imports here — configs serialise to JSON and round-trip
losslessly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "LossConfig",
    "LossKind",
    "OptimizerConfig",
    "OptimizerKind",
    "SchedulerConfig",
    "SchedulerKind",
    "TrainingConfig",
]


LossKind = Literal["cross_entropy", "weighted_cross_entropy", "focal", "ldam"]
OptimizerKind = Literal["sgd", "adam", "adamw"]
SchedulerKind = Literal["none", "cosine", "step"]


class LossConfig(BaseModel):
    """Loss-function hyperparameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: LossKind = "cross_entropy"
    # Per-class weights, broadcast against predictions. Optional.
    class_weights: tuple[float, ...] | None = None
    # Focal loss knobs.
    focal_alpha: float | None = Field(default=None, ge=0.0)
    focal_gamma: float = Field(default=2.0, ge=0.0)
    # LDAM knobs.
    ldam_max_m: float = Field(default=0.5, gt=0.0)
    ldam_scale: float = Field(default=30.0, gt=0.0)
    # Training-class counts (required for LDAM; optional for
    # weighted CE if ``class_weights`` is omitted).
    class_counts: tuple[int, ...] | None = None
    label_smoothing: float = Field(default=0.0, ge=0.0, lt=1.0)


class OptimizerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: OptimizerKind = "adamw"
    lr: float = Field(default=1e-3, gt=0.0)
    weight_decay: float = Field(default=1e-4, ge=0.0)
    momentum: float = Field(default=0.9, ge=0.0, lt=1.0)


class SchedulerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: SchedulerKind = "none"
    warmup_steps: int = Field(default=0, ge=0)
    # ``cosine`` uses ``t_max`` = number of total optimiser steps.
    t_max: int | None = Field(default=None, ge=1)
    # ``step`` uses ``step_size`` + ``gamma``.
    step_size: int | None = Field(default=None, ge=1)
    gamma: float = Field(default=0.1, gt=0.0, le=1.0)


class TrainingConfig(BaseModel):
    """Hyperparameters for a single supervised training run.

    The config intentionally excludes anything that identifies the
    dataset or the checkpoint path — those are passed as separate
    arguments to the node so the cache key is composed of:

    * the config hash,
    * the dataset content hash (cohort / tile set),
    * the model card identity.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_card: str = Field(min_length=1)
    num_classes: int = Field(ge=1)
    epochs: int = Field(default=1, ge=1)
    batch_size: int = Field(default=32, ge=1)
    seed: int = 0
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    precision: Literal["32", "16-mixed", "bf16-mixed"] = "32"
    num_workers: int = Field(default=0, ge=0)
    pretrained: bool = True
    # Subsections.
    loss: LossConfig = Field(default_factory=LossConfig)
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    # Calibration applied on a held-out validation split at end of training.
    calibrate: bool = True

    @model_validator(mode="after")
    def _loss_coherent_with_classes(self) -> TrainingConfig:
        if self.loss.class_weights is not None and len(self.loss.class_weights) != self.num_classes:
            raise ValueError(
                f"loss.class_weights length ({len(self.loss.class_weights)}) "
                f"must match num_classes ({self.num_classes})"
            )
        if self.loss.class_counts is not None and len(self.loss.class_counts) != self.num_classes:
            raise ValueError(
                f"loss.class_counts length ({len(self.loss.class_counts)}) "
                f"must match num_classes ({self.num_classes})"
            )
        if self.loss.kind == "ldam" and self.loss.class_counts is None:
            raise ValueError("LDAM loss requires loss.class_counts to be set")
        return self
