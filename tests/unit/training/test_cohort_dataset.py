"""CohortTileDataset — labels, tiling, and factory."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.io import Cohort, SlideRef
from openpathai.training import (
    CohortTileDataset,
    build_torch_dataset_from_cohort,
)

pytest.importorskip("torch")


def _cohort_with_labels() -> Cohort:
    return Cohort(
        id="demo",
        slides=(
            SlideRef(slide_id="a", path="/tmp/a.svs", label="normal"),
            SlideRef(slide_id="b", path="/tmp/b.svs", label="tumour"),
            SlideRef(slide_id="c", path="/tmp/c.svs", label="normal"),
            SlideRef(slide_id="d", path="/tmp/d.svs", label=None),
        ),
    )


def _provider(slide, idx):
    rng = np.random.default_rng(abs(hash(slide.slide_id)) % (2**32))
    return (rng.random((96, 96, 3)) * 255).astype(np.uint8)


def test_cohort_dataset_drops_unlabelled() -> None:
    ds = CohortTileDataset(
        _cohort_with_labels(),
        class_names=("normal", "tumour"),
        tile_size=(32, 32),
        tile_provider=_provider,
    )
    assert len(ds) == 3  # slide 'd' has no label → dropped
    assert ds.class_names == ("normal", "tumour")


def test_cohort_dataset_label_mapping() -> None:
    ds = CohortTileDataset(
        _cohort_with_labels(),
        class_names=("normal", "tumour"),
        tile_size=(32, 32),
        tile_provider=_provider,
    )
    _, label_a = ds[0]  # slide 'a'
    _, label_b = ds[1]  # slide 'b'
    _, label_c = ds[2]  # slide 'c'
    assert label_a == 0  # 'normal'
    assert label_b == 1  # 'tumour'
    assert label_c == 0


def test_cohort_dataset_tiles_per_slide_expands_len() -> None:
    ds = CohortTileDataset(
        _cohort_with_labels(),
        class_names=("normal", "tumour"),
        tiles_per_slide=2,
        tile_size=(32, 32),
        tile_provider=_provider,
    )
    assert len(ds) == 6  # 3 labelled slides x 2 tiles


def test_cohort_dataset_rejects_unknown_class() -> None:
    with pytest.raises(ValueError, match="not in class_names"):
        CohortTileDataset(
            _cohort_with_labels(),
            class_names=("normal",),  # 'tumour' missing
            tile_provider=_provider,
        )


def test_cohort_dataset_rejects_empty_cohort() -> None:
    cohort = Cohort(
        id="empty",
        slides=(SlideRef(slide_id="a", path="/tmp/a.svs", label=None),),
    )
    with pytest.raises(ValueError, match="no slides with a label"):
        CohortTileDataset(
            cohort,
            class_names=("normal", "tumour"),
            tile_provider=_provider,
        )


def test_factory_returns_torch_dataset() -> None:
    import torch
    from torch.utils.data import Dataset

    ds = build_torch_dataset_from_cohort(
        _cohort_with_labels(),
        class_names=("normal", "tumour"),
        tile_size=(32, 32),
        tile_provider=_provider,
    )
    assert isinstance(ds, Dataset)
    assert len(ds) == 3
    tensor, label = ds[0]
    assert isinstance(tensor, torch.Tensor)
    assert tensor.shape == (3, 32, 32)
    assert label in (0, 1)


def test_cohort_dataset_rejects_bad_provider_output() -> None:
    def bad_provider(slide, idx):
        return np.zeros((8, 8), dtype=np.uint8)  # not RGB

    ds = CohortTileDataset(
        _cohort_with_labels(),
        class_names=("normal", "tumour"),
        tile_provider=bad_provider,
    )
    with pytest.raises(ValueError, match="must return"):
        ds[0]
