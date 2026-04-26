"""Train endpoint (Phase 20.5 → Phase 21.7 chunk A).

Enqueues a training job through the shared :class:`JobRunner` so the
canvas Train screen can submit + poll status.

Resolution path:

* ``synthetic=true`` (default, canvas demo) — deterministic in-process
  loop that emits real-shaped loss / accuracy / ECE points without any
  Tier-2+ deps. Useful as a smoke test.
* ``synthetic=false`` + dataset card has ``method='local'`` (typically
  written by ``register_folder`` after a local-source download) +
  ``[train]`` extra installed — runs the Phase-3 :class:`LightningTrainer`
  against the **real on-disk dataset**, capped to ``duration_preset``
  epochs, and persists the best checkpoint to
  ``$OPENPATHAI_HOME/checkpoints/<run_id>/``.
* ``synthetic=false`` but ``[train]`` missing — returns a structured
  ``mode='missing_backend'`` envelope so the canvas can prompt the user
  to install the right extra (Phase 21.7 chunk D).
* ``synthetic=false`` against a non-local card (Zenodo / Kaggle / HF) —
  records a clear ``mode='missing_local_card'`` error pointing the user
  at the wizard's local_source_path override (Phase 21.7 chunk C).
"""

from __future__ import annotations

import math
import os
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency
from openpathai.server.jobs import JobRunner

__all__ = ["TrainRequest", "router"]


_DURATION_EPOCHS: dict[str, int] = {
    "Quick": 2,
    "Standard": 10,
    "Thorough": 30,
}
"""Phase 21.7 chunk A — duration preset → epoch count."""

_QUICK_TILE_CAP = 256
"""For the Quick preset, cap the dataset at 256 random tiles so a
real laptop CPU finishes in a couple of minutes."""


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


def _missing_backend_envelope(req: TrainRequest, message: str, install_cmd: str) -> dict[str, Any]:
    """Structured response for the canvas when an optional extra is
    missing. The wizard renders ``install_cmd`` as a copy-able block
    instead of dumping the raw ImportError text."""
    return {
        "submitted": req.model_dump(mode="json"),
        "status": "error",
        "mode": "missing_backend",
        "message": message,
        "install_cmd": install_cmd,
        "epochs": [],
        "best": None,
    }


def _missing_local_card_envelope(req: TrainRequest, message: str) -> dict[str, Any]:
    """Real training requires a ``method='local'`` card. Surface the
    wizard's recovery path instead of crashing."""
    return {
        "submitted": req.model_dump(mode="json"),
        "status": "error",
        "mode": "missing_local_card",
        "message": message,
        "epochs": [],
        "best": None,
    }


def _checkpoints_root() -> Path:
    return Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai")) / "checkpoints"


def _real_train(req: TrainRequest, *, run_id: str | None = None) -> dict[str, Any]:
    """Real Lightning fit against the user's on-disk dataset card.

    Resolution:

    1. Look up the model card and the dataset card.
    2. Reject (with a structured ``missing_local_card`` envelope) any
       dataset whose ``download.method`` isn't ``local`` — real training
       happens against locally-available bytes only.
    3. Build a :class:`LocalDatasetTileDataset` from the symlinked
       folder. Optionally subsample to ``_QUICK_TILE_CAP`` for the
       Quick preset.
    4. Split 80/20 deterministically (numpy seed).
    5. Run :class:`LightningTrainer.fit` with epochs from the duration
       preset.
    6. Persist the best checkpoint under
       ``$OPENPATHAI_HOME/checkpoints/<run_id>/``.
    """
    try:
        import numpy as np

        from openpathai.data.registry import default_registry
        from openpathai.models.registry import default_model_registry
        from openpathai.training.config import OptimizerConfig, TrainingConfig
        from openpathai.training.datasets import (
            InMemoryTileBatch,
            LocalDatasetTileDataset,
        )
        from openpathai.training.engine import LightningTrainer
    except ImportError as exc:
        return _missing_backend_envelope(
            req,
            f"required runtime missing: {exc}",
            "uv sync --extra train --extra data",
        )

    try:
        model_card = default_model_registry().get(req.model)
    except Exception as exc:
        return _missing_local_card_envelope(
            req,
            f"model {req.model!r} is not in the registry; pick a card from /v1/models. ({exc})",
        )

    try:
        dataset_card = default_registry().get(req.dataset)
    except Exception as exc:
        return _missing_local_card_envelope(
            req,
            f"dataset {req.dataset!r} is not in the registry. "
            "If you just downloaded it, the wizard should have auto-registered it as "
            f"'<name>_local' — re-run the download step. ({exc})",
        )

    if dataset_card.download.method != "local":
        return _missing_local_card_envelope(
            req,
            f"dataset {req.dataset!r} uses download.method={dataset_card.download.method!r}. "
            "Real training needs a local-method card. In the wizard's download step, "
            "expand Advanced → Local source folder, then re-run download. The wizard "
            "auto-registers the symlinked folder as a local-method card.",
        )

    try:
        full_dataset = LocalDatasetTileDataset(
            dataset_card,
            tile_size=tuple(model_card.input_size),  # type: ignore[arg-type]
        )
    except (NotADirectoryError, ValueError) as exc:
        return _missing_local_card_envelope(req, str(exc))

    epochs_count = _DURATION_EPOCHS.get(req.duration_preset, req.epochs)

    rng_np = np.random.default_rng(req.seed)
    n_total = len(full_dataset)
    if n_total == 0:
        return _missing_local_card_envelope(
            req,
            f"dataset {req.dataset!r} resolved to {dataset_card.download.local_path} "
            "but contains no readable images.",
        )

    indices = np.arange(n_total)
    rng_np.shuffle(indices)
    if req.duration_preset == "Quick" and n_total > _QUICK_TILE_CAP:
        indices = indices[:_QUICK_TILE_CAP]

    pixels: list[np.ndarray] = []
    labels: list[int] = []
    for idx in indices.tolist():
        tile, label = full_dataset[int(idx)]
        pixels.append(tile)
        labels.append(label)
    pixels_arr = np.stack(pixels).astype(np.float32, copy=False)
    labels_arr = np.array(labels, dtype=np.int64)

    cut = max(1, round(0.8 * len(indices)))
    train_pixels, val_pixels = pixels_arr[:cut], pixels_arr[cut:]
    train_labels, val_labels = labels_arr[:cut], labels_arr[cut:]
    if len(val_pixels) == 0:
        val_pixels, val_labels = train_pixels, train_labels

    class_names = full_dataset.class_names
    num_classes = max(int(labels_arr.max()) + 1, len(class_names))

    train_batch = InMemoryTileBatch(
        pixels=train_pixels, labels=train_labels, class_names=class_names
    )
    val_batch = InMemoryTileBatch(pixels=val_pixels, labels=val_labels, class_names=class_names)

    checkpoint_dir = _checkpoints_root() / (run_id or "ad-hoc")
    config = TrainingConfig(
        model_card=model_card.name,
        epochs=epochs_count,
        batch_size=req.batch_size,
        seed=req.seed,
        num_classes=num_classes,
        pretrained=False,
        optimizer=OptimizerConfig(lr=req.learning_rate),
    )
    trainer = LightningTrainer(config, card=model_card, checkpoint_dir=checkpoint_dir)
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
        "dataset_path": str(dataset_card.download.local_path),
        "tiles_used": len(indices),
        "checkpoint_path": report.checkpoint_path,
        "epochs": epochs,
        "best": {
            "epoch": int(best["epoch"]),
            "val_accuracy": float(best.get("val_accuracy") or 0.0),
        },
    }


def _train_inline(req: TrainRequest, *, run_id: str | None = None) -> dict[str, Any]:
    if req.synthetic:
        return _synthetic_train(req)
    return _real_train(req, run_id=run_id)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a training run",
)
async def enqueue_train(request: Request, body: TrainRequest) -> dict[str, Any]:
    runner = _runner(request)
    run_id = uuid4().hex
    try:
        try:
            job = runner.submit(
                lambda: _train_inline(body, run_id=run_id),
                metadata={
                    "kind": "training",
                    "dataset": body.dataset,
                    "model": body.model,
                    "epochs": body.epochs,
                    "duration_preset": body.duration_preset,
                    "synthetic": body.synthetic,
                },
                run_id=run_id,
            )
        except TypeError:
            # Older JobRunner.submit signature without run_id.
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
        # Phase 21.7 chunk A — when the real path returned a structured
        # missing_backend / missing_local_card envelope, surface it as
        # an error to the polling client.
        if job.result.get("status") == "error":
            metrics["status"] = "error"
            metrics["error"] = job.result.get("message") or job.result.get("mode")
            if job.result.get("install_cmd"):
                metrics["install_cmd"] = job.result["install_cmd"]
    return metrics
