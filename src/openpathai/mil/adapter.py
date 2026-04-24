"""``MILAdapter`` protocol + associated artifact models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:  # pragma: no cover - type-only
    pass

__all__ = [
    "MILAdapter",
    "MILForwardOutput",
    "MILTrainingReport",
]


class MILForwardOutput(BaseModel):
    """Output of one forward pass on a bag of ``N`` tile embeddings."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    logits: np.ndarray  # shape (num_classes,)
    attention: np.ndarray  # shape (N,) sums to 1


class MILTrainingReport(BaseModel):
    """Result of one MIL fit call. Used by CLI + audit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    aggregator_id: str = Field(min_length=1)
    num_classes: int = Field(ge=2)
    embedding_dim: int = Field(ge=1)
    n_bags_train: int = Field(ge=1)
    epochs_run: int = Field(ge=1)
    final_train_loss: float = Field(ge=0.0)
    train_loss_curve: tuple[float, ...]


class MILAdapter(Protocol):
    """Minimal surface every MIL aggregator honours."""

    id: str
    embedding_dim: int
    num_classes: int

    def forward(self, bag: Any) -> MILForwardOutput: ...
    def fit(
        self,
        bags: list[Any],
        labels: Any,
        *,
        epochs: int,
        lr: float,
        seed: int,
    ) -> MILTrainingReport: ...
    def slide_heatmap(self, bag: Any, coords: Any) -> np.ndarray: ...
