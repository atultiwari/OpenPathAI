"""Active-learning loop driver (Phase 12).

A single ``ActiveLearningLoop.run()`` does the full cycle:

1. Train a seed model on a small labelled subset.
2. Score the remaining pool for uncertainty.
3. Pick the next batch (top-K uncertain, with optional diversity
   tie-break using the current model's embeddings).
4. Ask the :class:`Oracle` for the true labels → :class:`LabelCorrection`s.
5. Fold the new labels into the training set and retrain.
6. Evaluate on the held-out split → record ECE before/after.
7. Repeat until ``iterations`` exhausted or the pool is dry.

The :class:`Trainer` protocol abstracts the model so tests can plug
in a deterministic synthetic trainer while the CLI wires the Phase 3
timm+Lightning engine. The loop itself is **torch-free** — only the
concrete :class:`Trainer` touches torch.

PHI discipline:
* ``tile_id``s are opaque strings; the loop never touches pixel data
  paths or patient IDs.
* Every audit row uses the graph-hash ``sha256(config_dump || iter)``
  so Phase 8 dedupe does not coalesce iterations.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from openpathai.active_learning.corrections import CorrectionLogger
from openpathai.active_learning.diversity import k_center_greedy, random_indices
from openpathai.active_learning.oracle import Oracle
from openpathai.active_learning.uncertainty import SCORERS, UncertaintyScorer
from openpathai.training.metrics import accuracy, expected_calibration_error

__all__ = [
    "AcquisitionResult",
    "ActiveLearningConfig",
    "ActiveLearningLoop",
    "ActiveLearningRun",
    "LabelledExample",
    "Trainer",
    "TrainerFitResult",
]


ScorerName = Literal["max_softmax", "entropy", "mc_dropout"]
SamplerName = Literal["uncertainty", "diversity", "hybrid"]


@dataclass(frozen=True)
class LabelledExample:
    """Opaque reference to one labelled tile. The :class:`Trainer`
    turns the id into actual pixels; the loop only shuffles ids."""

    tile_id: str
    label: str


class TrainerFitResult(BaseModel):
    """What :meth:`Trainer.fit` returns each call."""

    model_config = ConfigDict(frozen=True, extra="allow")

    epochs_run: int = Field(ge=0)
    train_loss: float = Field(ge=0.0)


class Trainer(Protocol):
    """Minimal surface the loop needs from a model backend.

    Implementations:
    * hold their own random seed + reset to ``initial_weights`` before
      each :meth:`fit` call so acquisition experiments are repeatable;
    * expose stable ordering on ``classes`` (list of class labels).
    """

    classes: tuple[str, ...]

    def fit(
        self,
        labelled: Sequence[LabelledExample],
        *,
        max_epochs: int,
        seed: int,
    ) -> TrainerFitResult: ...

    def predict_proba(self, tile_ids: Sequence[str]) -> np.ndarray: ...

    def embed(self, tile_ids: Sequence[str]) -> np.ndarray: ...


class ActiveLearningConfig(BaseModel):
    """Frozen configuration for one AL run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(default_factory=lambda: f"al-{uuid.uuid4().hex[:12]}")
    dataset_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    scorer: ScorerName = "max_softmax"
    sampler: SamplerName = "uncertainty"
    diversity_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    seed_size: int = Field(default=16, ge=1)
    budget_per_iteration: int = Field(default=8, ge=1)
    iterations: int = Field(default=3, ge=1)
    holdout_fraction: float = Field(default=0.2, ge=0.0, le=0.9)
    max_epochs_per_round: int = Field(default=3, ge=1)
    random_seed: int = Field(default=1234, ge=0)
    annotator_id: str = Field(default="simulated-oracle", min_length=1)
    mc_dropout_passes: int = Field(default=10, ge=2)

    def config_hash(self) -> str:
        """Deterministic hash of the frozen dump (minus run_id)."""
        payload = self.model_dump(exclude={"run_id"})
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def iteration_graph_hash(self, iteration: int) -> str:
        """Graph hash for the audit row of one iteration (unique per
        iteration, so Phase 8 dedupe does not coalesce rows)."""
        return hashlib.sha256(f"{self.config_hash()}::iter={iteration}".encode()).hexdigest()


class AcquisitionResult(BaseModel):
    """Per-iteration snapshot of what changed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    iteration: int = Field(ge=0)
    selected_tile_ids: tuple[str, ...]
    ece_before: float = Field(ge=0.0)
    ece_after: float = Field(ge=0.0)
    accuracy_after: float = Field(ge=0.0, le=1.0)
    train_loss: float = Field(ge=0.0)


class ActiveLearningRun(BaseModel):
    """Final artifact written to ``out_dir/manifest.json``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    config: ActiveLearningConfig
    started_at: str
    finished_at: str
    acquisitions: tuple[AcquisitionResult, ...]
    initial_ece: float
    final_ece: float
    final_accuracy: float
    acquired_tile_ids: tuple[str, ...]


def _utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class ActiveLearningLoop:
    """Composition of primitives behind a single ``.run()`` entry point.

    The loop **does not** import torch. Audit-DB writes are also
    optional — tests pass ``audit_db=None`` to skip them.
    """

    def __init__(
        self,
        *,
        config: ActiveLearningConfig,
        trainer: Trainer,
        pool_tile_ids: Sequence[str],
        seed_examples: Sequence[LabelledExample],
        holdout_examples: Sequence[LabelledExample],
        oracle: Oracle,
        correction_logger: CorrectionLogger | None = None,
        audit_db: Any | None = None,
    ) -> None:
        self._config = config
        self._trainer = trainer
        self._oracle = oracle
        self._pool_ids: list[str] = list(pool_tile_ids)
        self._seed: list[LabelledExample] = list(seed_examples)
        self._holdout: list[LabelledExample] = list(holdout_examples)
        self._correction_logger = correction_logger
        self._audit_db = audit_db

        if not self._pool_ids:
            raise ValueError("pool_tile_ids must be non-empty")
        if not self._seed:
            raise ValueError("seed_examples must be non-empty")
        if not self._holdout:
            raise ValueError("holdout_examples must be non-empty")
        if config.scorer == "mc_dropout":
            # MC-dropout requires the trainer to expose variance forward.
            # We handle it separately in _score_pool.
            pass
        if config.scorer not in {"max_softmax", "entropy", "mc_dropout"}:
            raise ValueError(f"unknown scorer {config.scorer!r}")

        classes = tuple(self._trainer.classes)
        if len(classes) < 2:
            raise ValueError("trainer must expose at least 2 classes")
        self._class_to_idx: dict[str, int] = {c: i for i, c in enumerate(classes)}

    # ─── Public API ────────────────────────────────────────────────

    def run(self, out_dir: str | Path) -> ActiveLearningRun:
        """Execute the loop; write ``manifest.json`` under ``out_dir``."""
        out = Path(out_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        started = _utcnow_iso()

        acquired: list[LabelledExample] = list(self._seed)
        acquired_ids: set[str] = {x.tile_id for x in acquired}
        available: list[str] = [tid for tid in self._pool_ids if tid not in acquired_ids]
        acquisitions: list[AcquisitionResult] = []

        # Baseline train on the seed set.
        fit_result = self._trainer.fit(
            acquired,
            max_epochs=self._config.max_epochs_per_round,
            seed=self._config.random_seed,
        )
        initial_metrics = self._evaluate_holdout()
        initial_ece = initial_metrics["ece"]
        running_ece = initial_ece
        running_acc = initial_metrics["accuracy"]
        running_loss = fit_result.train_loss

        for it in range(self._config.iterations):
            if not available:
                break
            budget = min(self._config.budget_per_iteration, len(available))
            selected = self._select_batch(available, budget, iteration=it)

            predictions = self._current_predictions(selected)
            corrections = self._oracle.query(
                selected,
                predictions=predictions,
                iteration=it,
            )
            if self._correction_logger is not None:
                self._correction_logger.log(corrections)

            # Fold the new labels into the training set and retrain.
            acquired.extend(
                LabelledExample(tile_id=c.tile_id, label=c.corrected_label) for c in corrections
            )
            acquired_ids.update(c.tile_id for c in corrections)
            available = [tid for tid in available if tid not in acquired_ids]

            fit_result = self._trainer.fit(
                acquired,
                max_epochs=self._config.max_epochs_per_round,
                seed=self._config.random_seed + it + 1,
            )
            metrics = self._evaluate_holdout()

            result = AcquisitionResult(
                iteration=it,
                selected_tile_ids=tuple(selected),
                ece_before=running_ece,
                ece_after=metrics["ece"],
                accuracy_after=metrics["accuracy"],
                train_loss=fit_result.train_loss,
            )
            acquisitions.append(result)
            running_ece = metrics["ece"]
            running_acc = metrics["accuracy"]
            running_loss = fit_result.train_loss
            self._record_audit(result)

        finished = _utcnow_iso()
        run = ActiveLearningRun(
            run_id=self._config.run_id,
            config=self._config,
            started_at=started,
            finished_at=finished,
            acquisitions=tuple(acquisitions),
            initial_ece=initial_ece,
            final_ece=running_ece,
            final_accuracy=running_acc,
            acquired_tile_ids=tuple(sorted(acquired_ids)),
        )
        (out / "manifest.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
        # running_loss is surfaced on each AcquisitionResult; kept here
        # as a sanity anchor for debugging inspection.
        del running_loss
        return run

    # ─── Internals ─────────────────────────────────────────────────

    def _select_batch(
        self,
        available: Sequence[str],
        budget: int,
        *,
        iteration: int,
    ) -> list[str]:
        """Pick ``budget`` tile ids from ``available`` using the
        configured scorer + sampler combination."""
        scores = self._score_pool(available)
        sampler = self._config.sampler
        seed = self._config.random_seed + iteration + 1

        if sampler == "uncertainty":
            order = np.argsort(-scores, kind="stable")
            return [available[int(i)] for i in order[:budget]]
        if sampler == "diversity":
            embeddings = self._trainer.embed(list(available))
            picks = k_center_greedy(embeddings, budget)
            return [available[int(i)] for i in picks]
        if sampler == "hybrid":
            # Pool the top-`shortlist` uncertain, then diversify via
            # k-center inside that shortlist.
            shortlist_size = min(len(available), max(budget * 3, budget))
            order = np.argsort(-scores, kind="stable")
            shortlist_idx = order[:shortlist_size]
            shortlist_ids = [available[int(i)] for i in shortlist_idx]
            embeddings = self._trainer.embed(shortlist_ids)
            picks = k_center_greedy(embeddings, budget)
            return [shortlist_ids[int(i)] for i in picks]
        # Fallback to random (never reached under pydantic validation,
        # but kept as a belt-and-braces safety rail).
        picks = random_indices(len(available), budget, seed=seed)  # pragma: no cover
        return [available[int(i)] for i in picks]  # pragma: no cover

    def _score_pool(self, tile_ids: Sequence[str]) -> np.ndarray:
        """Per-sample uncertainty scores over ``tile_ids``."""
        if self._config.scorer == "mc_dropout":
            stacked = self._mc_dropout_probs(tile_ids)
            from openpathai.active_learning.uncertainty import mc_dropout_variance

            return mc_dropout_variance(stacked)
        scorer: UncertaintyScorer = SCORERS[self._config.scorer]
        probs = self._trainer.predict_proba(list(tile_ids))
        return scorer(probs)

    def _mc_dropout_probs(self, tile_ids: Sequence[str]) -> np.ndarray:
        """Fallback stacker for trainers that don't ship their own
        stochastic forward. Simply calls ``predict_proba`` ``N`` times
        — the trainer is responsible for dropout-in-eval semantics.
        """
        passes = self._config.mc_dropout_passes
        first = self._trainer.predict_proba(list(tile_ids))
        stacked = np.empty((passes, *first.shape), dtype=np.float64)
        stacked[0] = first
        for i in range(1, passes):
            stacked[i] = self._trainer.predict_proba(list(tile_ids))
        return stacked

    def _current_predictions(self, tile_ids: Sequence[str]) -> Mapping[str, str]:
        probs = self._trainer.predict_proba(list(tile_ids))
        best = probs.argmax(axis=1)
        classes = list(self._trainer.classes)
        return {tid: classes[int(idx)] for tid, idx in zip(tile_ids, best, strict=True)}

    def _evaluate_holdout(self) -> dict[str, float]:
        tile_ids = [x.tile_id for x in self._holdout]
        probs = self._trainer.predict_proba(tile_ids)
        y_true = np.asarray(
            [self._class_to_idx[x.label] for x in self._holdout],
            dtype=np.int64,
        )
        y_pred = probs.argmax(axis=1).astype(np.int64)
        return {
            "ece": float(expected_calibration_error(probs, y_true)),
            "accuracy": float(accuracy(y_true, y_pred)),
        }

    def _record_audit(self, result: AcquisitionResult) -> None:
        if self._audit_db is None:
            return
        metrics = {
            "al_iteration": result.iteration,
            "al_scorer": self._config.scorer,
            "al_sampler": self._config.sampler,
            "al_budget": self._config.budget_per_iteration,
            "annotator_id": self._config.annotator_id,
            "ece_before": result.ece_before,
            "ece_after": result.ece_after,
            "accuracy_after": result.accuracy_after,
            "train_loss": result.train_loss,
        }
        self._audit_db.insert_run(
            kind="pipeline",
            mode="exploratory",
            pipeline_yaml_hash=self._config.config_hash(),
            graph_hash=self._config.iteration_graph_hash(result.iteration),
            tier="local",
            status="success",
            metrics=metrics,
        )
