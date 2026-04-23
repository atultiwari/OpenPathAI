"""Tests for :mod:`openpathai.data.splits`.

Iron rule #4 invariant: no patient overlap across folds.
"""

from __future__ import annotations

import random

import pytest

from openpathai.data.splits import patient_level_kfold, patient_level_split


@pytest.mark.unit
def test_kfold_no_patient_overlap_many_seeds() -> None:
    patients = [f"p{i}" for i in range(40)]
    for seed in range(100):
        folds = patient_level_kfold(patients, n_splits=5, seed=seed)
        assert len(folds) == 5
        val_union: set[str] = set()
        for fold in folds:
            assert set(fold.train).isdisjoint(fold.val), (
                f"seed={seed} fold={fold.index} train∩val not empty"
            )
            val_union |= set(fold.val)
        # Every patient is in exactly one validation fold.
        assert val_union == set(patients)


@pytest.mark.unit
def test_kfold_deterministic_same_seed() -> None:
    patients = [f"p{i}" for i in range(20)]
    a = patient_level_kfold(patients, n_splits=4, seed=7)
    b = patient_level_kfold(patients, n_splits=4, seed=7)
    assert a == b


@pytest.mark.unit
def test_kfold_different_seed_shuffles() -> None:
    patients = [f"p{i}" for i in range(20)]
    a = patient_level_kfold(patients, n_splits=4, seed=1)
    b = patient_level_kfold(patients, n_splits=4, seed=2)
    assert a != b


@pytest.mark.unit
def test_kfold_requires_min_n_splits() -> None:
    with pytest.raises(ValueError, match=">= 2"):
        patient_level_kfold(["a", "b", "c"], n_splits=1)


@pytest.mark.unit
def test_kfold_too_few_patients_raises() -> None:
    with pytest.raises(ValueError, match="unique patients"):
        patient_level_kfold(["p1", "p2", "p3"], n_splits=5)


@pytest.mark.unit
def test_kfold_stratified_labels() -> None:
    patients = [f"p{i}" for i in range(20)]
    labels = ["pos" if i < 10 else "neg" for i in range(20)]
    folds = patient_level_kfold(patients, n_splits=5, seed=0, labels=labels)
    # Each fold should contain at least one positive and one negative
    # patient when classes are balanced 10/10 across 5 folds.
    for fold in folds:
        lab_set = {labels[patients.index(pid)] for pid in fold.val}
        assert {"pos", "neg"}.issubset(lab_set)


@pytest.mark.unit
def test_kfold_same_patient_duplicate_samples_still_disjoint() -> None:
    # Patients duplicated (one patient contributing many tiles) must
    # not cause cross-fold leakage.
    rng = random.Random(0)
    pids = [f"p{rng.randint(0, 19)}" for _ in range(500)]
    folds = patient_level_kfold(pids, n_splits=5, seed=0)
    for fold in folds:
        assert set(fold.train).isdisjoint(fold.val)


@pytest.mark.unit
def test_three_way_split_disjoint_and_covers_all() -> None:
    patients = [f"p{i}" for i in range(30)]
    train, val, test = patient_level_split(patients, train=0.7, val=0.15, test=0.15, seed=11)
    assert set(train).isdisjoint(val)
    assert set(train).isdisjoint(test)
    assert set(val).isdisjoint(test)
    assert set(train) | set(val) | set(test) == set(patients)


@pytest.mark.unit
def test_three_way_split_requires_fractions_to_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        patient_level_split(["a", "b", "c"], train=0.5, val=0.3, test=0.3)


@pytest.mark.unit
def test_three_way_split_requires_three_patients() -> None:
    with pytest.raises(ValueError, match="at least 3 unique"):
        patient_level_split(["a", "b"])
