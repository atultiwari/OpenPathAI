"""Train endpoint (Phase 20.5 + Phase 21 refinement #1).

Enqueues a training job through the shared :class:`JobRunner` so the
canvas Train screen can submit + poll status.

Phase 20.5 shipped a stub that returned ``{"status": "queued"}``. Phase
21 refinement #1 promotes it to a real loop:

* ``synthetic=true`` (the canvas demo default) runs a deterministic
  in-process trainer that emits real loss / accuracy metric points so
  the Train dashboard renders something meaningful without pulling
  Tier-2+ deps.
* ``synthetic=false`` + ``[train]`` extra installed runs the Phase-3
  :class:`LightningTrainer` against a small in-memory synthetic
  ``InMemoryTileBatch``. Real datasets are still routed through the
  CLI (``openpathai train --dataset``) to keep the request hot path
  bounded; the goal here is to validate the Lightning chain inside
  the canvas without pinning CI to a long fit.
* If ``synthetic=false`` and ``[train]`` is missing the job records a
  clear error per iron rule #11.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency
from openpathai.server.jobs import JobRunner

__all__ = ["TrainRequest", "router"]


router = APIRouter(prefix="/train", tags=["train"], dependencies=[AuthDependency])


class TrainRequest(BaseModel):
    """Train-tab payload (Easy / Standard / Expert all collapse here)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset: str = Field(min_length=1)
    model: str = Field(min_length=1)
    epochs: int = Field(default=1, ge=1, le=200)
    batch_size: int = Field(default=32, ge=1, le=1024)
    learning_rate: float = Field(default=1e-3, gt=0.0, le=1.0)
    seed: int = Field(default=0, ge=0)
    synthetic: bool = Field(default=True)
    duration_preset: str = Field(default="Standard")


def _runner(request: Request) -> JobRunner:
    runner = getattr(request.app.state, "job_runner", None)
    if runner is None:
        runner = JobRunner(max_workers=request.app.state.settings.max_concurrent_runs)
        request.app.state.job_runner = runner
    return runner


def _synthetic_train(
    req: TrainRequest, *, sleep: Callable[[float], None] = time.sleep
) -> dict[str, Any]:
    """Deterministic synthetic loop. Emits real loss / val_accuracy /
    ECE points so the Train dashboard has something to render even
    without ``[train]``.

    The shape mirrors the real Lightning report so the front-end does
    not need a switch — fields are the same; the ``mode`` field tells
    the user which path produced them.
    """
    rng = random.Random(req.seed)
    base = 1.6 + 0.4 * rng.random()
    epochs: list[dict[str, Any]] = []
    for i in range(req.epochs):
        # Loss decays exponentially toward a floor that depends on the seed
        # so different seeds give visibly different curves.
        train_loss = base * math.exp(-(i + 1) * 0.5) + 0.05 * rng.random()
        val_loss = train_loss * (0.95 + 0.1 * rng.random())
        val_acc = 1.0 - math.exp(-(i + 1) * 0.4) - 0.02 * rng.random()
        val_acc = max(0.0, min(1.0, val_acc))
        ece = max(0.0, 0.2 * math.exp(-(i + 1) * 0.3) + 0.01 * rng.random())
        epochs.append(
            {
                "epoch": i,
                "train_loss": float(round(train_loss, 4)),
                "val_loss": float(round(val_loss, 4)),
                "val_accuracy": float(round(val_acc, 4)),
                "ece": float(round(ece, 4)),
            }
        )
        # Tiny sleep so polling shows progressive growth in tests.
        sleep(0.0)
    return {
        "submitted": req.model_dump(mode="json"),
        "status": "succeeded",
        "mode": "synthetic",
        "epochs": epochs,
        "best": {
            "epoch": int(max(range(len(epochs)), key=lambda i: epochs[i]["val_accuracy"])),
            "val_accuracy": float(max(e["val_accuracy"] for e in epochs)),
        },
    }


def _real_train(req: TrainRequest) -> dict[str, Any]:
    """Phase-3 Lightning fit against a small synthetic in-memory batch.

    Real datasets are still routed through ``openpathai train``; this
    path exists so the canvas Train tab can verify that the Lightning
    chain is wired correctly inside the running server. The model card
    is resolved through the existing model registry (no inline card
    construction — the registry is the source of truth for card schema).
    """
    try:
        import numpy as np

        from openpathai.models.registry import default_model_registry
        from openpathai.training.config import TrainingConfig
        from openpathai.training.datasets import InMemoryTileBatch
        from openpathai.training.engine import LightningTrainer
    except Exception as exc:
        raise RuntimeError("training extras not installed; run `uv sync --extra train`.") from exc

    try:
        registry = default_model_registry()
        card = registry.get(req.model)
    except Exception as exc:
        raise RuntimeError(
            f"model {req.model!r} is not in the registry; pick a card from /v1/models."
        ) from exc

    # Tiny synthetic batch — 16 RGB tiles, 2 classes.
    rng = np.random.default_rng(req.seed)
    n, ch = 16, 3
    h, w = card.input_size
    pixels = rng.random((n, ch, h, w)).astype("float32")
    labels = rng.integers(0, 2, size=(n,)).astype("int64")
    class_names = ("class_0", "class_1")
    train_batch = InMemoryTileBatch(pixels=pixels, labels=labels, class_names=class_names)
    val_batch = InMemoryTileBatch(pixels=pixels[:8], labels=labels[:8], class_names=class_names)

    from openpathai.training.config import OptimizerConfig

    config = TrainingConfig(
        model_card=card.name,
        epochs=req.epochs,
        batch_size=req.batch_size,
        seed=req.seed,
        num_classes=2,
        pretrained=False,
        optimizer=OptimizerConfig(lr=req.learning_rate),
    )
    trainer = LightningTrainer(config, card=card)
    report = trainer.fit(train=train_batch, val=val_batch)
    epochs = [
        {
            "epoch": rec.epoch,
            "train_loss": float(rec.train_loss),
            "val_loss": float(rec.val_loss) if rec.val_loss is not None else None,
            "val_accuracy": float(rec.val_accuracy) if rec.val_accuracy is not None else None,
            "ece": float(rec.val_ece) if rec.val_ece is not None else None,
        }
        for rec in report.history
    ]
    best = max(
        epochs,
        key=lambda e: e["val_accuracy"] if e["val_accuracy"] is not None else -1.0,
        default={"epoch": 0, "val_accuracy": 0.0},
    )
    return {
        "submitted": req.model_dump(mode="json"),
        "status": "succeeded",
        "mode": "lightning",
        "epochs": epochs,
        "best": {
            "epoch": int(best["epoch"]),
            "val_accuracy": float(best.get("val_accuracy") or 0.0),
        },
    }


def _train_inline(req: TrainRequest) -> dict[str, Any]:
    if req.synthetic:
        return _synthetic_train(req)
    return _real_train(req)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a training run",
)
async def enqueue_train(request: Request, body: TrainRequest) -> dict[str, Any]:
    runner = _runner(request)
    try:
        job = runner.submit(
            lambda: _train_inline(body),
            metadata={
                "kind": "training",
                "dataset": body.dataset,
                "model": body.model,
                "epochs": body.epochs,
                "duration_preset": body.duration_preset,
                "synthetic": body.synthetic,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return job.to_public()


@router.get(
    "/runs/{run_id}/metrics",
    summary="Polling metrics for a queued / running / finished training job",
)
async def train_metrics(request: Request, run_id: str) -> dict[str, Any]:
    runner = _runner(request)
    job = runner.get(run_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run {run_id!r} not found",
        )
    metrics: dict[str, Any] = {
        "run_id": run_id,
        "status": job.status,
        "metadata": dict(job.metadata),
        "error": job.error,
    }
    if job.status == "success" and isinstance(job.result, dict):
        metrics["result"] = job.result
        metrics["epochs"] = job.result.get("epochs", [])
        metrics["best"] = job.result.get("best")
        metrics["mode"] = job.result.get("mode")
    return metrics
