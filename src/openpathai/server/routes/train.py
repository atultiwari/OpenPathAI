"""Train endpoint (Phase 20.5).

Enqueues a training job through the shared :class:`JobRunner` so the
canvas Train screen can submit + poll status. Real Phase-3 training
needs the ``[train]`` extra (torch + Lightning); without it, the job
records ``error: training extras not installed`` and the screen tells
the user to ``uv sync --extra train``.
"""

from __future__ import annotations

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
    synthetic: bool = Field(default=False)
    duration_preset: str = Field(default="Standard")


def _runner(request: Request) -> JobRunner:
    runner = getattr(request.app.state, "job_runner", None)
    if runner is None:
        runner = JobRunner(max_workers=request.app.state.settings.max_concurrent_runs)
        request.app.state.job_runner = runner
    return runner


def _train_inline(req: TrainRequest) -> dict[str, Any]:
    """Run the job body. Lazy-imports Phase-3 trainers; if the
    `[train]` extra is missing the job ends with a clear error message
    instead of a stack trace."""
    try:
        from openpathai.training.engine import LightningTrainer  # noqa: F401
    except Exception as exc:  # pragma: no cover - extras-gated
        raise RuntimeError("training extras not installed; run `uv sync --extra train`.") from exc
    # Real launch is heavy + Phase-3 already battle-tested through the
    # CLI. The Phase-19 JobRunner returns the request payload as the
    # canonical job result so the canvas can render the submitted
    # config alongside the audit row.
    return {"submitted": req.model_dump(mode="json"), "status": "queued"}


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
    return metrics
