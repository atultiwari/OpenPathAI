"""Supervised training engine — Tier A (Phase 3).

Every training run is driven by :class:`TrainingConfig` and exposed via
the :func:`openpathai.training.node.train` pipeline node. The math
(losses, metrics, calibration) is implemented in pure numpy so the
module is importable — and unit-testable — without torch.
"""

from __future__ import annotations

from openpathai.training.artifacts import (
    EpochRecord,
    TrainingReportArtifact,
)
from openpathai.training.calibration import (
    TemperatureScaler,
    apply_temperature,
)
from openpathai.training.config import (
    LossConfig,
    OptimizerConfig,
    SchedulerConfig,
    TrainingConfig,
)
from openpathai.training.datasets import (
    InMemoryTileBatch,
    build_torch_dataset,
    synthetic_tile_batch,
)
from openpathai.training.engine import (
    LightningTrainer,
    TileClassifierModule,
    resolve_device,
)
from openpathai.training.losses import (
    cross_entropy_loss,
    focal_loss,
    ldam_loss,
    log_softmax_numpy,
    softmax_numpy,
)
from openpathai.training.metrics import (
    accuracy,
    confusion_matrix,
    expected_calibration_error,
    macro_f1,
    reliability_bins,
)
from openpathai.training.node import (
    TrainingNodeInput,
    clear_batches,
    hash_batch,
    lookup_batch,
    register_batch,
    train,
)

__all__ = [
    "EpochRecord",
    "InMemoryTileBatch",
    "LightningTrainer",
    "LossConfig",
    "OptimizerConfig",
    "SchedulerConfig",
    "TemperatureScaler",
    "TileClassifierModule",
    "TrainingConfig",
    "TrainingNodeInput",
    "TrainingReportArtifact",
    "accuracy",
    "apply_temperature",
    "build_torch_dataset",
    "clear_batches",
    "confusion_matrix",
    "cross_entropy_loss",
    "expected_calibration_error",
    "focal_loss",
    "hash_batch",
    "ldam_loss",
    "log_softmax_numpy",
    "lookup_batch",
    "macro_f1",
    "register_batch",
    "reliability_bins",
    "resolve_device",
    "softmax_numpy",
    "synthetic_tile_batch",
    "train",
]
