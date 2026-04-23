"""Torch-facing dataset adapters used by the Phase 3 training engine.

Phase 3 covers the minimal path: in-memory numpy tile tensors wrapped
as a ``torch.utils.data.Dataset``. Real cohort loading (slides + tiles
on disk via the Phase 2 primitives) lands in Phase 5 alongside the CLI
driver.

The module is importable without torch; any function that actually
needs torch imports it lazily.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - type hints only
    pass

__all__ = [
    "InMemoryTileBatch",
    "build_torch_dataset",
    "synthetic_tile_batch",
]


@dataclass(frozen=True)
class InMemoryTileBatch:
    """A tiny in-memory batch of tiles + labels.

    ``pixels`` is stored as a ``(N, C, H, W)`` float32 array in ``[0, 1]``
    already normalised (mean-subtraction / std-division should be baked
    in before the batch is constructed so the dataset stays deterministic).
    """

    pixels: np.ndarray
    labels: np.ndarray
    class_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.pixels.ndim != 4:
            raise ValueError(f"pixels must be 4D (N, C, H, W); got shape {self.pixels.shape}")
        if self.labels.ndim != 1:
            raise ValueError(f"labels must be 1D; got shape {self.labels.shape}")
        if self.pixels.shape[0] != self.labels.shape[0]:
            raise ValueError("pixels and labels disagree on N")
        if self.pixels.dtype != np.float32:
            raise ValueError(f"pixels must be float32; got {self.pixels.dtype}")

    @property
    def num_classes(self) -> int:
        return len(self.class_names)


def synthetic_tile_batch(
    *,
    num_classes: int = 4,
    samples_per_class: int = 16,
    tile_size: tuple[int, int] = (32, 32),
    seed: int = 0,
) -> InMemoryTileBatch:
    """Generate a tiny deterministic multi-class tile batch for tests.

    Each class gets a distinct mean RGB colour so a linear classifier
    can learn the task in a handful of steps. The signal is strong
    enough to exercise the engine end-to-end on CPU without noise.
    """
    rng = np.random.default_rng(seed)
    h, w = tile_size
    pixels = np.zeros((num_classes * samples_per_class, 3, h, w), dtype=np.float32)
    labels = np.zeros(num_classes * samples_per_class, dtype=np.int64)
    for cls in range(num_classes):
        # Distinct per-class mean colour in [0.2, 0.8].
        mean = 0.2 + 0.6 * rng.random(3)
        for i in range(samples_per_class):
            idx = cls * samples_per_class + i
            noise = rng.normal(loc=0.0, scale=0.05, size=(3, h, w)).astype(np.float32)
            pixels[idx] = np.clip(mean[:, None, None] + noise, 0.0, 1.0).astype(np.float32)
            labels[idx] = cls
    class_names = tuple(f"class_{i}" for i in range(num_classes))
    return InMemoryTileBatch(pixels=pixels, labels=labels, class_names=class_names)


def build_torch_dataset(batch: InMemoryTileBatch) -> Any:  # pragma: no cover
    """Wrap an :class:`InMemoryTileBatch` as a ``torch.utils.data.Dataset``.

    Raises ``ImportError`` if torch is not installed. Torch-gated; the
    integration test exercises this when the ``[train]`` extra is
    installed.
    """
    try:
        import torch
        from torch.utils.data import TensorDataset
    except ImportError as exc:
        raise ImportError(
            "Building a torch dataset requires the 'torch' package. "
            "Install it via the [train] extra: `uv sync --extra train`."
        ) from exc

    tensors = torch.from_numpy(batch.pixels.copy())
    targets = torch.from_numpy(batch.labels.copy()).long()
    return TensorDataset(tensors, targets)
