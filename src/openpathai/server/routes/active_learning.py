"""Active-learning queue endpoints (Phase 20.5, Bet 1 surface).

The canvas Annotate screen drives a *demo session* against the
Phase-12 :class:`PrototypeTrainer` so a pathologist can see the loop
shape without a full WSI pipeline behind it. A future phase plugs the
same endpoints into a real per-cohort trainer.

Three endpoints:
- ``POST /v1/active-learning/sessions`` — start a new demo session
  (synchronous; returns the loop manifest).
- ``GET /v1/active-learning/sessions`` — list sessions stored under
  ``$OPENPATHAI_HOME/active-learning/``.
- ``GET /v1/active-learning/sessions/{session_id}`` — fetch one
  session's manifest.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency

__all__ = ["StartSessionRequest", "router"]


router = APIRouter(
    prefix="/active-learning",
    tags=["active-learning"],
    dependencies=[AuthDependency],
)


_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]+$")


class StartSessionRequest(BaseModel):
    """Demo session config — uses the Phase-12 PrototypeTrainer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    classes: tuple[str, ...] = Field(min_length=2, max_length=8)
    pool_size: int = Field(default=64, ge=8, le=2048)
    seed_size: int = Field(default=8, ge=2, le=64)
    holdout_size: int = Field(default=16, ge=4, le=256)
    iterations: int = Field(default=2, ge=1, le=10)
    budget_per_iteration: int = Field(default=4, ge=1, le=64)
    scorer: str = Field(default="max_softmax")
    diversity_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    random_seed: int = Field(default=1234, ge=0)


def _root(request: Request) -> Path:
    root = request.app.state.settings.openpathai_home / "active-learning"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe(session_id: str) -> str:
    if not _SAFE_ID.match(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid session id {session_id!r}",
        )
    return session_id


def _session_dir(request: Request, session_id: str) -> Path:
    return _root(request) / _safe(session_id)


def _read_manifest(session_dir: Path) -> dict[str, Any] | None:
    manifest = session_dir / "manifest.json"
    if not manifest.is_file():
        return None
    return json.loads(manifest.read_text(encoding="utf-8"))


@router.get("/sessions", summary="List demo active-learning sessions")
async def list_sessions(request: Request) -> dict[str, Any]:
    root = _root(request)
    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()) if root.is_dir() else []:
        if not child.is_dir():
            continue
        manifest = _read_manifest(child)
        items.append({"id": child.name, "manifest": manifest})
    return {"items": items, "total": len(items)}


@router.get(
    "/sessions/{session_id}",
    summary="Retrieve one demo active-learning session",
)
async def get_session(request: Request, session_id: str) -> dict[str, Any]:
    session_dir = _session_dir(request, session_id)
    manifest = _read_manifest(session_dir)
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"session {session_id!r} not found",
        )
    return {"id": session_id, "manifest": manifest}


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    summary="Run a Phase-12 demo active-learning loop end-to-end",
)
async def create_session(request: Request, body: StartSessionRequest) -> dict[str, Any]:
    """Spin up a synthetic demo loop using the Phase-12
    :class:`PrototypeTrainer` + :func:`build_oracle_for_tests`. The
    canvas Annotate screen surfaces the resulting iteration metrics so
    the pathologist can inspect the loop shape; real interactive
    labeling lands in a later phase.
    """
    from openpathai.active_learning.corrections import CorrectionLogger
    from openpathai.active_learning.loop import (
        ActiveLearningConfig,
        ActiveLearningLoop,
        LabelledExample,
    )
    from openpathai.active_learning.oracle import build_oracle_for_tests
    from openpathai.active_learning.synthetic import PrototypeTrainer

    classes = tuple(body.classes)
    pool_ids = [f"tile-{i:04d}" for i in range(body.pool_size)]
    # Round-robin labels for the synthetic oracle.
    label_pairs = [(tid, classes[i % len(classes)]) for i, tid in enumerate(pool_ids)]
    seed = [LabelledExample(tile_id=tid, label=lbl) for tid, lbl in label_pairs[: body.seed_size]]
    holdout = [
        LabelledExample(tile_id=tid, label=lbl)
        for tid, lbl in label_pairs[body.seed_size : body.seed_size + body.holdout_size]
    ]

    config = ActiveLearningConfig(
        dataset_id="synthetic-demo",
        model_id="prototype-trainer",
        scorer=body.scorer,  # type: ignore[arg-type]
        diversity_weight=body.diversity_weight,
        seed_size=body.seed_size,
        budget_per_iteration=body.budget_per_iteration,
        iterations=body.iterations,
        random_seed=body.random_seed,
    )

    session_id = config.run_id
    out_dir = _session_dir(request, session_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    oracle = build_oracle_for_tests(label_pairs, tmp_path=out_dir)
    trainer = PrototypeTrainer(classes=classes, embedding_dim=16)
    correction_logger = CorrectionLogger(out_dir / "corrections.csv")

    loop = ActiveLearningLoop(
        config=config,
        trainer=trainer,
        pool_tile_ids=pool_ids,
        seed_examples=seed,
        holdout_examples=holdout,
        oracle=oracle,
        correction_logger=correction_logger,
        audit_db=None,
    )
    try:
        run = loop.run(out_dir)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return {"id": session_id, "manifest": run.model_dump(mode="json")}
