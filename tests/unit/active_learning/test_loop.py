"""Phase 12 — ActiveLearningLoop end-to-end with the synthetic trainer."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pytest

from openpathai.active_learning import (
    ActiveLearningConfig,
    ActiveLearningLoop,
    CorrectionLogger,
    LabelledExample,
    PrototypeTrainer,
)
from openpathai.active_learning.oracle import build_oracle_for_tests
from openpathai.safety.audit import AuditDB


def _pool(n: int, classes: tuple[str, ...], seed: int) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    return [(f"tile-{i:04d}", rng.choice(classes)) for i in range(n)]


def _label_signal(
    rows: list[tuple[str, str]], classes: tuple[str, ...], seed: int, dim: int = 16
) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    anchors = {c: rng.standard_normal(dim) for c in classes}
    out: dict[str, np.ndarray] = {}
    for tid, lbl in rows:
        out[tid] = anchors[lbl] + 0.25 * rng.standard_normal(dim)
    return out


def _build(
    tmp_path: Path,
    *,
    n: int = 120,
    classes: tuple[str, ...] = ("a", "b", "c"),
    scorer: str = "max_softmax",
    sampler: str = "uncertainty",
    iterations: int = 3,
    budget: int = 6,
    audit_db: AuditDB | None = None,
) -> tuple[ActiveLearningLoop, Path]:
    rows = _pool(n, classes, seed=1)
    signal = _label_signal(rows, classes, seed=1)
    rng = random.Random(1)
    shuffled = list(rows)
    rng.shuffle(shuffled)
    holdout_rows = shuffled[:20]
    seed_rows = shuffled[20:32]
    pool_rows = shuffled[32:]

    oracle = build_oracle_for_tests(rows, tmp_path=tmp_path)
    trainer = PrototypeTrainer(classes=classes, label_signal=signal, feature_seed=1)
    out = tmp_path / "run"
    config = ActiveLearningConfig(
        dataset_id="test-ds",
        model_id="proto",
        scorer=scorer,  # type: ignore[arg-type]
        sampler=sampler,  # type: ignore[arg-type]
        seed_size=len(seed_rows),
        budget_per_iteration=budget,
        iterations=iterations,
        holdout_fraction=0.2,
        max_epochs_per_round=1,
        random_seed=1,
    )
    loop = ActiveLearningLoop(
        config=config,
        trainer=trainer,
        pool_tile_ids=[t for t, _ in pool_rows],
        seed_examples=[LabelledExample(tile_id=t, label=lbl) for t, lbl in seed_rows],
        holdout_examples=[LabelledExample(tile_id=t, label=lbl) for t, lbl in holdout_rows],
        oracle=oracle,
        correction_logger=CorrectionLogger(out / "corrections.csv"),
        audit_db=audit_db,
    )
    return loop, out


def test_loop_runs_and_ece_does_not_worsen(tmp_path: Path) -> None:
    loop, out = _build(tmp_path)
    run = loop.run(out)
    assert (out / "manifest.json").exists()
    assert (out / "corrections.csv").exists()
    assert len(run.acquisitions) == 3
    assert run.final_ece <= run.initial_ece + 1e-9
    # Monitored accuracy must stay on [0, 1].
    assert 0.0 <= run.final_accuracy <= 1.0


def test_manifest_round_trip(tmp_path: Path) -> None:
    loop, out = _build(tmp_path)
    run = loop.run(out)
    payload = json.loads((out / "manifest.json").read_text())
    assert payload["run_id"] == run.run_id
    assert len(payload["acquisitions"]) == len(run.acquisitions)
    assert payload["acquired_tile_ids"] == list(run.acquired_tile_ids)


def test_corrections_csv_cardinality(tmp_path: Path) -> None:
    loop, out = _build(tmp_path, iterations=2, budget=5)
    loop.run(out)
    rows = (out / "corrections.csv").read_text().splitlines()
    # 1 header + 2 iterations, 5 corrections each
    assert len(rows) == 1 + 2 * 5


def test_diversity_sampler(tmp_path: Path) -> None:
    loop, out = _build(tmp_path, sampler="diversity", iterations=2, budget=4)
    run = loop.run(out)
    assert len(run.acquisitions) == 2
    # Selected ids must be unique across all iterations.
    all_ids: list[str] = []
    for acq in run.acquisitions:
        all_ids.extend(acq.selected_tile_ids)
    assert len(all_ids) == len(set(all_ids))


def test_hybrid_sampler(tmp_path: Path) -> None:
    loop, out = _build(tmp_path, sampler="hybrid", iterations=2, budget=4)
    run = loop.run(out)
    assert len(run.acquisitions) == 2


def test_mc_dropout_scorer(tmp_path: Path) -> None:
    # The synthetic trainer is deterministic, so mc_dropout_variance is
    # all zeros — but the loop must still complete and fall back to a
    # stable tiebreak order without crashing.
    loop, out = _build(tmp_path, scorer="mc_dropout", iterations=2, budget=4)
    run = loop.run(out)
    assert len(run.acquisitions) == 2


def test_audit_db_receives_one_row_per_iteration(tmp_path: Path) -> None:
    db = AuditDB.open_path(tmp_path / "audit.db")
    loop, out = _build(tmp_path, iterations=3, budget=4, audit_db=db)
    loop.run(out)
    rows = db.list_runs(kind="pipeline")
    # Each iteration should produce one row with a distinct graph hash.
    assert len(rows) == 3
    hashes = {r.graph_hash for r in rows}
    assert len(hashes) == 3


def test_loop_rejects_empty_seed(tmp_path: Path) -> None:
    oracle = build_oracle_for_tests([("t-0", "a"), ("t-1", "b")], tmp_path=tmp_path)
    trainer = PrototypeTrainer(classes=("a", "b"))
    config = ActiveLearningConfig(
        dataset_id="d", model_id="m", budget_per_iteration=1, iterations=1
    )
    with pytest.raises(ValueError, match="seed_examples"):
        ActiveLearningLoop(
            config=config,
            trainer=trainer,
            pool_tile_ids=["t-0", "t-1"],
            seed_examples=[],
            holdout_examples=[LabelledExample(tile_id="t-1", label="b")],
            oracle=oracle,
        )


def test_loop_rejects_empty_holdout(tmp_path: Path) -> None:
    oracle = build_oracle_for_tests([("t-0", "a"), ("t-1", "b")], tmp_path=tmp_path)
    trainer = PrototypeTrainer(classes=("a", "b"))
    config = ActiveLearningConfig(
        dataset_id="d", model_id="m", budget_per_iteration=1, iterations=1
    )
    with pytest.raises(ValueError, match="holdout_examples"):
        ActiveLearningLoop(
            config=config,
            trainer=trainer,
            pool_tile_ids=["t-0", "t-1"],
            seed_examples=[LabelledExample(tile_id="t-0", label="a")],
            holdout_examples=[],
            oracle=oracle,
        )


def test_config_hash_changes_with_fields() -> None:
    a = ActiveLearningConfig(dataset_id="d", model_id="m", budget_per_iteration=1, iterations=1)
    b = ActiveLearningConfig(dataset_id="d", model_id="m", budget_per_iteration=2, iterations=1)
    assert a.config_hash() != b.config_hash()
    # run_id is excluded from the hash.
    c = ActiveLearningConfig(
        dataset_id="d",
        model_id="m",
        budget_per_iteration=1,
        iterations=1,
        run_id="differs",
    )
    assert a.config_hash() == c.config_hash()
    assert a.iteration_graph_hash(0) != a.iteration_graph_hash(1)
