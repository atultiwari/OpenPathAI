"""LocalDatasetTileDataset + build_torch_dataset_from_card."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from openpathai.data import register_folder
from openpathai.training import (
    LocalDatasetTileDataset,
    build_torch_dataset_from_card,
)

pytest.importorskip("torch")


@pytest.fixture
def imagefolder(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    for cls in ("normal", "tumour"):
        (root / cls).mkdir(parents=True)
        for i in range(2):
            arr = np.random.default_rng(i + hash(cls) % 100).integers(
                0, 255, (32, 32, 3), dtype=np.uint8
            )
            Image.fromarray(arr).save(root / cls / f"{cls}_{i}.png")
    return root


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))


def test_local_dataset_shapes(imagefolder: Path) -> None:
    card = register_folder(imagefolder, name="p9_unit", tissue=("colon",))
    ds = LocalDatasetTileDataset(card, tile_size=(64, 64))
    assert len(ds) == 4
    assert ds.class_names == ("normal", "tumour")
    pixels, label = ds[0]
    assert pixels.shape == (3, 64, 64)
    assert pixels.dtype == np.float32
    assert label in {0, 1}


def test_local_dataset_rejects_non_local_card() -> None:
    from openpathai.data import default_registry

    lc = default_registry().get("lc25000")
    with pytest.raises(ValueError, match="method='local'"):
        LocalDatasetTileDataset(lc)


def test_build_torch_dataset_from_card_returns_torch_dataset(imagefolder: Path) -> None:
    card = register_folder(imagefolder, name="p9_unit2", tissue=("colon",))
    ds = build_torch_dataset_from_card(card, tile_size=(32, 32))
    import torch
    from torch.utils.data import Dataset

    assert isinstance(ds, Dataset)
    assert len(ds) == 4
    tensor, _label = ds[0]
    assert isinstance(tensor, torch.Tensor)
    assert tensor.shape == (3, 32, 32)


def test_build_torch_dataset_from_card_rejects_kaggle_method() -> None:
    from openpathai.data import default_registry

    lc = default_registry().get("lc25000")
    with pytest.raises(NotImplementedError, match="Phase 10"):
        build_torch_dataset_from_card(lc)


def test_missing_local_path_raises(tmp_path: Path) -> None:
    """A card whose local_path no longer exists on disk must fail fast."""
    os.environ["OPENPATHAI_HOME"] = str(tmp_path / "home2")
    # Build a fresh ImageFolder for registration.
    fresh = tmp_path / "tree_fresh"
    for cls in ("a", "b"):
        (fresh / cls).mkdir(parents=True)
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(fresh / cls / f"{cls}.png")
    card = register_folder(fresh, name="p9_missing", tissue=("colon",))
    # Now remove the folder.
    import shutil

    shutil.rmtree(fresh)
    with pytest.raises(NotADirectoryError):
        LocalDatasetTileDataset(card)
