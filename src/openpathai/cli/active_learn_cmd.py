"""``openpathai active-learn`` — Phase 12 CLI entry point.

Reads a **pool CSV** (columns: ``tile_id``, ``label``) which serves as
both the universe of tile ids *and* the ground-truth oracle. Splits
the pool into seed / unlabeled / holdout, then drives
:class:`openpathai.active_learning.ActiveLearningLoop` with the
torch-free :class:`~openpathai.active_learning.synthetic.PrototypeTrainer`
so the command completes in seconds on any machine — no torch install
required.

This shape intentionally mirrors ``openpathai train --synthetic``
from Phase 3: the CLI is correct end-to-end on its own, and the
production path (real timm backbone on an LC25000 cohort) lands with
the Annotate GUI in Phase 16.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import numpy as np
import typer

from openpathai.active_learning import (
    ActiveLearningConfig,
    ActiveLearningLoop,
    CorrectionLogger,
    CSVOracle,
    LabelledExample,
    PrototypeTrainer,
)
from openpathai.safety.audit import AuditDB

__all__ = ["register"]


def register(app: typer.Typer) -> None:
    @app.command("active-learn")
    def active_learn(
        pool: Annotated[
            Path,
            typer.Option(
                "--pool",
                help=(
                    "CSV with columns ``tile_id,label`` listing the full pool. "
                    "Rows double as the simulated oracle's ground truth."
                ),
            ),
        ],
        out: Annotated[
            Path,
            typer.Option(
                "--out",
                help="Output directory for manifest.json + corrections.csv.",
            ),
        ],
        dataset: Annotated[
            str,
            typer.Option(
                "--dataset",
                help="Dataset identifier (free text; recorded in the manifest).",
            ),
        ] = "synthetic",
        model: Annotated[
            str,
            typer.Option(
                "--model",
                help="Model identifier (free text; recorded in the manifest).",
            ),
        ] = "prototype-synthetic",
        scorer: Annotated[
            str,
            typer.Option(
                "--scorer",
                help="Uncertainty scorer: max_softmax | entropy | mc_dropout.",
            ),
        ] = "max_softmax",
        sampler: Annotated[
            str,
            typer.Option(
                "--sampler",
                help="Batch sampler: uncertainty | diversity | hybrid.",
            ),
        ] = "uncertainty",
        seed_size: Annotated[
            int,
            typer.Option(
                "--seed-size",
                min=1,
                help="Number of examples in the initial labelled set.",
            ),
        ] = 12,
        budget: Annotated[
            int,
            typer.Option(
                "--budget",
                min=1,
                help="Number of new labels acquired per iteration.",
            ),
        ] = 8,
        iterations: Annotated[
            int,
            typer.Option(
                "--iterations",
                min=1,
                help="Number of AL iterations.",
            ),
        ] = 3,
        holdout_fraction: Annotated[
            float,
            typer.Option(
                "--holdout",
                min=0.0,
                max=0.9,
                help="Fraction of the pool held out for ECE evaluation.",
            ),
        ] = 0.25,
        annotator_id: Annotated[
            str,
            typer.Option(
                "--annotator-id",
                help="Annotator tag logged with every correction row.",
            ),
        ] = "simulated-oracle",
        random_seed: Annotated[
            int,
            typer.Option(
                "--seed",
                min=0,
                help="Deterministic seed driving the seed/holdout split.",
            ),
        ] = 1234,
        no_audit: Annotated[
            bool,
            typer.Option(
                "--no-audit",
                help=(
                    "Skip writing one audit row per iteration. Useful for "
                    "ephemeral smoke runs; leave on (default) to record the "
                    "run under ~/.openpathai/audit.db."
                ),
            ),
        ] = False,
    ) -> None:
        """Run a simulated-oracle active-learning loop on a pool CSV."""
        try:
            rows = _load_pool_csv(pool)
        except ValueError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2) from exc
        if scorer not in {"max_softmax", "entropy", "mc_dropout"}:
            typer.secho(
                f"unknown scorer {scorer!r} (allowed: max_softmax, entropy, mc_dropout)",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)
        if sampler not in {"uncertainty", "diversity", "hybrid"}:
            typer.secho(
                f"unknown sampler {sampler!r} (allowed: uncertainty, diversity, hybrid)",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)

        out = out.expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)

        classes = sorted({r[1] for r in rows})
        if len(classes) < 2:
            typer.secho(
                f"pool CSV must contain at least 2 distinct labels; found {classes}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)

        seed_examples, pool_unlabeled, holdout_examples = _split_pool(
            rows,
            seed_size=seed_size,
            holdout_fraction=holdout_fraction,
            seed=random_seed,
        )
        if budget > len(pool_unlabeled):
            typer.secho(
                f"budget {budget} exceeds unlabeled pool size {len(pool_unlabeled)} "
                "after seed/holdout carve-out; shrink --budget or --seed-size.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)

        oracle = CSVOracle(pool, annotator_id=annotator_id)

        config = ActiveLearningConfig(
            dataset_id=dataset,
            model_id=model,
            scorer=scorer,  # type: ignore[arg-type]
            sampler=sampler,  # type: ignore[arg-type]
            seed_size=seed_size,
            budget_per_iteration=budget,
            iterations=iterations,
            holdout_fraction=holdout_fraction,
            max_epochs_per_round=1,
            random_seed=random_seed,
            annotator_id=annotator_id,
        )
        label_signal = _label_signal(rows, classes, dim=16, seed=random_seed)
        trainer = PrototypeTrainer(
            classes=classes,
            embedding_dim=16,
            feature_seed=random_seed,
            label_signal=label_signal,
        )
        correction_logger = CorrectionLogger(out / "corrections.csv")
        audit_db = None if no_audit else AuditDB.open_default()
        loop = ActiveLearningLoop(
            config=config,
            trainer=trainer,
            pool_tile_ids=[tid for tid, _ in pool_unlabeled],
            seed_examples=seed_examples,
            holdout_examples=holdout_examples,
            oracle=oracle,
            correction_logger=correction_logger,
            audit_db=audit_db,
        )

        typer.echo(
            f"Running AL loop · dataset={dataset} model={model} "
            f"scorer={scorer} sampler={sampler} iterations={iterations} "
            f"budget/iter={budget}",
            err=True,
        )
        result = loop.run(out)

        summary = {
            "run_id": result.run_id,
            "iterations_completed": len(result.acquisitions),
            "initial_ece": round(result.initial_ece, 6),
            "final_ece": round(result.final_ece, 6),
            "delta_ece": round(result.final_ece - result.initial_ece, 6),
            "final_accuracy": round(result.final_accuracy, 6),
            "n_acquired": len(result.acquired_tile_ids) - seed_size,
            "annotator_id": annotator_id,
            "out_dir": str(out),
            "manifest_path": str(out / "manifest.json"),
            "corrections_path": str(out / "corrections.csv"),
        }
        typer.echo(json.dumps(summary, indent=2))


def _load_pool_csv(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        raise ValueError(f"pool CSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "tile_id" not in reader.fieldnames:
            raise ValueError("pool CSV must contain a 'tile_id' column")
        if "label" not in reader.fieldnames:
            raise ValueError("pool CSV must contain a 'label' column")
        rows: list[tuple[str, str]] = []
        for row in reader:
            tid = (row.get("tile_id") or "").strip()
            lbl = (row.get("label") or "").strip()
            if tid and lbl:
                rows.append((tid, lbl))
    if len(rows) < 4:
        raise ValueError(f"pool CSV {path} has only {len(rows)} usable rows; need at least 4")
    return rows


def _split_pool(
    rows: Sequence[tuple[str, str]],
    *,
    seed_size: int,
    holdout_fraction: float,
    seed: int,
) -> tuple[list[LabelledExample], list[tuple[str, str]], list[LabelledExample]]:
    rng = random.Random(seed)
    shuffled = list(rows)
    rng.shuffle(shuffled)
    n_holdout = max(1, round(len(shuffled) * holdout_fraction))
    holdout_rows = shuffled[:n_holdout]
    remainder = shuffled[n_holdout:]
    if seed_size >= len(remainder):
        raise ValueError(
            f"seed_size {seed_size} leaves no room for an unlabeled pool "
            f"(remainder={len(remainder)})"
        )
    seed_rows = remainder[:seed_size]
    unlabeled = remainder[seed_size:]
    seed_examples = [LabelledExample(tile_id=t, label=lbl) for t, lbl in seed_rows]
    holdout_examples = [LabelledExample(tile_id=t, label=lbl) for t, lbl in holdout_rows]
    return seed_examples, unlabeled, holdout_examples


def _label_signal(
    rows: Sequence[tuple[str, str]],
    classes: Sequence[str],
    *,
    dim: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Per-class directional anchor so the synthetic trainer actually
    learns — each tile's signal is a noisy version of its class
    prototype. Deterministic under ``seed``.
    """
    rng = np.random.default_rng(seed)
    anchors = {c: rng.standard_normal(dim) for c in classes}
    out: dict[str, np.ndarray] = {}
    for tid, lbl in rows:
        # Mild per-tile jitter on top of the class anchor so tiles are
        # not literally identical within a class.
        jitter_seed = int.from_bytes(hashlib.sha256(f"{seed}::{tid}".encode()).digest()[:8], "big")
        jitter_rng = np.random.default_rng(jitter_seed)
        out[tid] = anchors[lbl] + 0.3 * jitter_rng.standard_normal(dim)
    return out
