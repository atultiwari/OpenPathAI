"""Torch-facing dataset adapters used by the Phase 3+ training engine.

Phase 3 covers the minimal synthetic path. Phase 9 extends with real
dataset loaders:

* :class:`LocalDatasetTileDataset` — reads Phase 7 ``method: "local"``
  dataset cards. Each class subdirectory under
  ``card.download.local_path`` maps to a class index.
* :class:`CohortTileDataset` — reads tiles out of a
  :class:`~openpathai.io.cohort.Cohort` via a caller-supplied tile
  provider; labels come from ``SlideRef.label``.
* :func:`build_torch_dataset_from_card` — dispatcher that the CLI +
  GUI Train tab both call.

The module is importable without torch; any function that actually
needs torch imports it lazily.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - type-only
    from openpathai.data.cards import DatasetCard
    from openpathai.io.cohort import Cohort, SlideRef

__all__ = [
    "CohortTileDataset",
    "InMemoryTileBatch",
    "LocalDatasetTileDataset",
    "build_torch_dataset",
    "build_torch_dataset_from_card",
    "build_torch_dataset_from_cohort",
    "synthetic_tile_batch",
]


_IMAGE_EXTS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".tif", ".tiff")


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


# --------------------------------------------------------------------------- #
# Phase 9 — real-cohort / real-card datasets
# --------------------------------------------------------------------------- #


def _resize_rgb(image: np.ndarray, tile_size: tuple[int, int]) -> np.ndarray:
    """Bilinear resize of an ``(H, W, 3)`` uint8 array.

    Uses Pillow (already a core dependency). Returns a contiguous
    ``(H, W, 3)`` uint8 array at the requested size.
    """
    from PIL import Image

    h, w = tile_size
    img = Image.fromarray(image, mode="RGB").resize((w, h), Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.uint8)


def _rgb_to_normalised_tensor(
    image: np.ndarray,
    *,
    tile_size: tuple[int, int],
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406),
    std: tuple[float, float, float] = (0.229, 0.224, 0.225),
) -> np.ndarray:
    """``(H, W, 3)`` uint8 → ``(3, H, W)`` float32, ImageNet-normalised."""
    resized = _resize_rgb(image, tile_size)
    arr = resized.astype(np.float32) / 255.0
    arr = (arr - np.asarray(mean, dtype=np.float32)) / np.asarray(std, dtype=np.float32)
    return np.transpose(arr, (2, 0, 1)).astype(np.float32)


def _scan_imagefolder(
    root: Path,
    classes: Sequence[str] | None = None,
) -> tuple[tuple[str, ...], list[tuple[Path, int]]]:
    """Return ``(class_names, [(path, label_idx), ...])`` for ``root``."""
    if classes is None:
        subdirs = sorted(
            p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
        class_names = tuple(subdirs)
    else:
        class_names = tuple(classes)

    items: list[tuple[Path, int]] = []
    for idx, cls in enumerate(class_names):
        class_dir = root / cls
        if not class_dir.is_dir():
            continue
        for p in sorted(class_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in _IMAGE_EXTS:
                items.append((p, idx))
    return class_names, items


class LocalDatasetTileDataset:
    """Torch-compatible tile dataset backed by a Phase 7 local card.

    Deliberately does *not* subclass :class:`torch.utils.data.Dataset`
    at import time — the class is usable without torch installed
    (``__len__`` / ``__getitem__`` return numpy), and the
    :func:`build_torch_dataset_from_card` factory wraps an instance in
    a torch ``Dataset`` shim when torch is present.
    """

    def __init__(
        self,
        card: DatasetCard,
        *,
        tile_size: tuple[int, int] = (224, 224),
        classes: Sequence[str] | None = None,
        mean: tuple[float, float, float] = (0.485, 0.456, 0.406),
        std: tuple[float, float, float] = (0.229, 0.224, 0.225),
    ) -> None:
        if card.download.method != "local":
            raise ValueError(
                f"LocalDatasetTileDataset only handles method='local' cards; "
                f"got {card.download.method!r} for {card.name!r}"
            )
        if card.download.local_path is None:
            raise ValueError(f"Card {card.name!r} has method='local' but no local_path set")
        root = Path(card.download.local_path).expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(
                f"Local card {card.name!r} points at {root} which is not a directory"
            )
        selected = classes if classes is not None else card.classes
        class_names, items = _scan_imagefolder(root, selected)
        if not items:
            raise ValueError(f"No images found under {root} for classes {class_names}")
        self._card = card
        self._root = root
        self._items = tuple(items)
        self._class_names = class_names
        self._tile_size = tile_size
        self._mean = mean
        self._std = std

    @property
    def class_names(self) -> tuple[str, ...]:
        return self._class_names

    @property
    def num_classes(self) -> int:
        return len(self._class_names)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> tuple[np.ndarray, int]:
        path, label = self._items[index]
        from PIL import Image

        with Image.open(path) as raw:
            rgb = np.asarray(raw.convert("RGB"), dtype=np.uint8)
        tensor = _rgb_to_normalised_tensor(
            rgb,
            tile_size=self._tile_size,
            mean=self._mean,
            std=self._std,
        )
        return tensor, int(label)


class CohortTileDataset:
    """Tile dataset over a :class:`~openpathai.io.cohort.Cohort`.

    One tile per slide (the mid-slide crop) by default — sufficient
    for the Phase 9 smoke path. Callers that need a denser tiling
    pass ``tiles_per_slide`` and a custom ``tile_provider``. Labels
    are taken from :attr:`SlideRef.label`; slides with no label are
    dropped.

    The ``tile_provider`` signature is
    ``(slide: SlideRef, index: int) -> np.ndarray`` — monkeypatchable
    in tests. The default provider uses
    :func:`openpathai.io.open_slide` + ``read_region`` at the slide's
    native magnification.
    """

    def __init__(
        self,
        cohort: Cohort,
        *,
        class_names: Sequence[str],
        tile_size: tuple[int, int] = (224, 224),
        tiles_per_slide: int = 1,
        tile_provider: Any = None,
        mean: tuple[float, float, float] = (0.485, 0.456, 0.406),
        std: tuple[float, float, float] = (0.229, 0.224, 0.225),
    ) -> None:
        if tiles_per_slide <= 0:
            raise ValueError("tiles_per_slide must be positive")

        name_to_idx = {name: idx for idx, name in enumerate(class_names)}
        labelled: list[SlideRef] = []
        for slide in cohort.slides:
            if slide.label is None:
                continue
            if slide.label not in name_to_idx:
                raise ValueError(
                    f"Slide {slide.slide_id!r} has label {slide.label!r} "
                    f"which is not in class_names {class_names}"
                )
            labelled.append(slide)
        if not labelled:
            raise ValueError(
                f"Cohort {cohort.id!r} has no slides with a label; nothing to train on"
            )

        self._cohort = cohort
        self._slides = tuple(labelled)
        self._class_names = tuple(class_names)
        self._name_to_idx = name_to_idx
        self._tile_size = tile_size
        self._tiles_per_slide = tiles_per_slide
        self._tile_provider = tile_provider or _default_tile_provider
        self._mean = mean
        self._std = std

    @property
    def class_names(self) -> tuple[str, ...]:
        return self._class_names

    @property
    def num_classes(self) -> int:
        return len(self._class_names)

    def __len__(self) -> int:
        return len(self._slides) * self._tiles_per_slide

    def __getitem__(self, index: int) -> tuple[np.ndarray, int]:
        slide_idx, tile_idx = divmod(index, self._tiles_per_slide)
        slide = self._slides[slide_idx]
        raw = self._tile_provider(slide, tile_idx)
        if raw.ndim != 3 or raw.shape[2] < 3:
            raise ValueError(f"tile_provider must return an (H, W, 3) RGB array; got {raw.shape}")
        tensor = _rgb_to_normalised_tensor(
            raw.astype(np.uint8),
            tile_size=self._tile_size,
            mean=self._mean,
            std=self._std,
        )
        label = self._name_to_idx[slide.label]  # type: ignore[arg-type]
        return tensor, int(label)


def _default_tile_provider(slide: SlideRef, _tile_idx: int) -> np.ndarray:
    """Fallback provider — reads a centre tile via the Phase 2 reader.

    Lazy-imports :mod:`openpathai.io.wsi` so importing
    :mod:`openpathai.training.datasets` stays light.
    """
    from openpathai.io import open_slide

    with open_slide(slide.path) as reader:
        info = reader.info
        side = min(info.width, info.height, 1024)
        x = max(0, (info.width - side) // 2)
        y = max(0, (info.height - side) // 2)
        region = reader.read_region(
            location=(x, y),
            size=(side, side),
            level=0,
        )
    return np.asarray(region, dtype=np.uint8)


# --------------------------------------------------------------------------- #
# Factories
# --------------------------------------------------------------------------- #


def _torch_dataset_shim(inner: Any) -> Any:
    """Wrap ``inner`` (which quacks like a dataset) in a torch.Dataset.

    Converts numpy tensors returned by ``inner[i]`` to torch tensors
    lazily so torch import is only paid on instantiation. Propagates
    ``class_names`` / ``num_classes`` through so downstream consumers
    (the :class:`LightningTrainer` report, the Train tab) can read them.
    """
    import torch
    from torch.utils.data import Dataset

    class _TileDataset(Dataset):
        def __init__(self) -> None:
            self._inner = inner
            # Mirror the class-level metadata so the trainer can name
            # the head's output axis when it builds the report.
            self.class_names = tuple(getattr(inner, "class_names", ()))
            self.num_classes = int(getattr(inner, "num_classes", len(self.class_names) or 0))

        def __len__(self) -> int:
            return len(self._inner)

        def __getitem__(self, idx: int) -> tuple[Any, int]:
            arr, label = self._inner[idx]
            return torch.from_numpy(np.ascontiguousarray(arr)), int(label)

    return _TileDataset()


def build_torch_dataset_from_card(
    card: DatasetCard,
    *,
    tile_size: tuple[int, int] = (224, 224),
    classes: Sequence[str] | None = None,
) -> Any:
    """Build a torch Dataset for a :class:`DatasetCard`.

    Dispatches on ``card.download.method``:
    * ``"local"`` → :class:`LocalDatasetTileDataset`.
    * anything else → :class:`NotImplementedError` with a Phase-10
      pointer (Kaggle / Zenodo loaders land alongside the
      orchestration work).
    """
    method = card.download.method
    if method != "local":
        raise NotImplementedError(
            f"Training directly from method={method!r} cards is not yet "
            "supported. Phase 10 will wire up Kaggle / Zenodo / HTTP "
            "downloaders and re-use this factory. For now, use the "
            "Phase 7 CLI to register a local copy: "
            "`openpathai datasets register <path> --name ...`."
        )
    inner = LocalDatasetTileDataset(card, tile_size=tile_size, classes=classes)
    return _torch_dataset_shim(inner)


def build_torch_dataset_from_cohort(
    cohort: Cohort,
    *,
    class_names: Sequence[str],
    tile_size: tuple[int, int] = (224, 224),
    tiles_per_slide: int = 1,
    tile_provider: Any = None,
) -> Any:
    """Build a torch Dataset for a :class:`Cohort`."""
    inner = CohortTileDataset(
        cohort,
        class_names=class_names,
        tile_size=tile_size,
        tiles_per_slide=tiles_per_slide,
        tile_provider=tile_provider,
    )
    return _torch_dataset_shim(inner)
