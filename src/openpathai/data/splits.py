"""Patient-level splits and k-fold cross-validation.

Iron rule #4 (``CLAUDE.md`` §2): any split helper that leaks a patient
across folds is a bug. Every split function here operates **on patient
IDs**, never on sample IDs, and returns fold assignments that partition
the patient set disjointly.

The helpers are deliberately dependency-light (stdlib + numpy) so they
can be used in Phase 3's training engine without pulling in scikit-learn.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

__all__ = [
    "PatientFold",
    "patient_level_kfold",
    "patient_level_split",
]


@dataclass(frozen=True)
class PatientFold:
    """One fold of a patient-level k-fold split.

    ``train`` and ``val`` hold patient IDs; downstream code maps those
    back to samples. Cross-checking ``set(train).isdisjoint(val)`` is a
    unit-test invariant.
    """

    index: int
    train: tuple[str, ...]
    val: tuple[str, ...]


def _stable_hash(text: str, seed: int) -> int:
    """Deterministic, cross-process int hash of a string.

    Python's built-in ``hash`` is salt-randomised per process; we rely on
    SHA-256 so splits are reproducible across machines and runs.
    """
    digest = hashlib.sha256(f"{seed}:{text}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _unique_sorted(patients: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(patients)))


def patient_level_kfold(
    patients: Sequence[str],
    *,
    n_splits: int = 5,
    seed: int = 0,
    labels: Sequence[str] | None = None,
) -> tuple[PatientFold, ...]:
    """Deterministic patient-level k-fold.

    Parameters
    ----------
    patients
        Patient IDs, one per sample (duplicates allowed — the same
        patient can contribute many tiles).
    n_splits
        Number of folds. Must be ``>= 2``.
    seed
        Deterministic seed. Same seed + same patient set → same folds.
    labels
        Optional same-length label sequence used for *balanced*
        stratification across folds. When given, each fold holds roughly
        proportional class representation.

    Returns
    -------
    tuple[PatientFold, ...]
        ``n_splits`` folds, each listing disjoint train/val patient IDs.

    Raises
    ------
    ValueError
        If ``n_splits < 2`` or there are fewer unique patients than
        folds.
    """
    if n_splits < 2:
        raise ValueError(f"n_splits must be >= 2, got {n_splits}")

    unique = _unique_sorted(patients)
    if len(unique) < n_splits:
        raise ValueError(
            f"Need at least {n_splits} unique patients for {n_splits}-fold; " f"got {len(unique)}"
        )

    # Stratified assignment: bucket by modal class per patient so that
    # every fold sees roughly the same class distribution. Without
    # labels, the single bucket degenerates to a global shuffle.
    buckets: dict[str, list[str]] = defaultdict(list)
    if labels is not None:
        if len(labels) != len(patients):
            raise ValueError("labels and patients must be the same length")
        patient_label: dict[str, str] = {}
        label_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for pid, lab in zip(patients, labels, strict=True):
            label_counts[pid][lab] += 1
        for pid, counts in label_counts.items():
            patient_label[pid] = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
        for pid in unique:
            buckets[patient_label[pid]].append(pid)
    else:
        buckets[""] = list(unique)

    # Deterministic shuffle within each bucket using the SHA-256 hash.
    for bucket in buckets.values():
        bucket.sort(key=lambda pid: _stable_hash(pid, seed))

    # Round-robin assign into folds so each fold gets a proportional
    # slice of every class bucket.
    fold_patients: list[list[str]] = [[] for _ in range(n_splits)]
    for bucket in buckets.values():
        for i, pid in enumerate(bucket):
            fold_patients[i % n_splits].append(pid)

    folds: list[PatientFold] = []
    for idx, val_set in enumerate(fold_patients):
        train_set = [pid for pid in unique if pid not in set(val_set)]
        folds.append(
            PatientFold(
                index=idx,
                train=tuple(sorted(train_set)),
                val=tuple(sorted(val_set)),
            )
        )
    return tuple(folds)


def patient_level_split(
    patients: Sequence[str],
    *,
    train: float = 0.7,
    val: float = 0.15,
    test: float = 0.15,
    seed: int = 0,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Deterministic patient-level train/val/test split.

    Returns three disjoint tuples of patient IDs summing to the unique
    patient set.
    """
    total = train + val + test
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"train+val+test must sum to 1.0 (got {total:.4f})")
    if any(x < 0 for x in (train, val, test)):
        raise ValueError("split fractions must be non-negative")

    unique = _unique_sorted(patients)
    if len(unique) < 3:
        raise ValueError(f"Need at least 3 unique patients for a 3-way split; got {len(unique)}")

    shuffled = sorted(unique, key=lambda pid: _stable_hash(pid, seed))
    n = len(shuffled)
    n_train = int(round(train * n))
    n_val = int(round(val * n))
    # Clamp so the remainder goes to test and every bucket has ≥1 when
    # fractions are non-zero.
    n_train = max(1, min(n_train, n - 2))
    n_val = max(1, min(n_val, n - n_train - 1)) if val > 0 else 0
    train_pids = tuple(sorted(shuffled[:n_train]))
    val_pids = tuple(sorted(shuffled[n_train : n_train + n_val]))
    test_pids = tuple(sorted(shuffled[n_train + n_val :]))
    return train_pids, val_pids, test_pids
