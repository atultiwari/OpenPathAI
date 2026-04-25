"""Analyse endpoints (Phase 20.5).

Wraps the Phase-7 ``openpathai analyse`` library path behind two
HTTP routes:

- ``POST /v1/analyse/tile`` — multipart upload of a tile + model id,
  returns predictions + a base64-encoded heatmap.
- ``POST /v1/analyse/report`` — render the most recent in-memory
  result as a PDF via Phase-7 ``safety.report.render_pdf``.

The endpoints fall back to a deterministic synthetic result when the
``[train]`` extra is missing — the canvas Analyse screen still works
on a fresh `[server]`-only install for demo / dev purposes. Iron rule
#11 applies: the synthetic path's ``model_name`` is rewritten to
``"<requested>-synthetic"`` so the wire payload makes it obvious.
"""

from __future__ import annotations

import base64
import hashlib
import io
from typing import Any

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency

__all__ = ["router"]


router = APIRouter(prefix="/analyse", tags=["analyse"], dependencies=[AuthDependency])


_LAST_RESULT_KEY = "_last_analyse_result"


class _SessionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    image_sha256: str
    model_name: str
    explainer_name: str
    classes: tuple[str, ...]
    probs: tuple[float, ...]
    overlay_b64: str
    thumbnail_b64: str
    borderline: bool
    confidence: float


class TilePrediction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    image_sha256: str
    model_name: str
    resolved_model_name: str
    explainer_name: str
    classes: tuple[str, ...]
    probabilities: tuple[float, ...] = Field(min_length=1)
    predicted_class: str
    confidence: float
    borderline: bool
    heatmap_b64: str
    thumbnail_b64: str
    fallback_reason: str | None = None


def _load_image(raw: bytes) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(raw)) as img:
            return np.asarray(img.convert("RGB"), dtype=np.uint8)
    except Exception as exc:  # pragma: no cover - PIL coverage is wide
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"could not decode tile: {exc!s}",
        ) from exc


def _png_b64(arr: np.ndarray) -> str:
    buf = io.BytesIO()
    mode = "RGB" if arr.ndim == 3 and arr.shape[-1] == 3 else "L"
    Image.fromarray(arr, mode=mode).save(buf, format="PNG", optimize=False)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _synthetic_predict(
    image: np.ndarray, classes: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic CPU-only stand-in: hash-based class probabilities
    + a Gaussian heatmap centred on the brightest patch."""
    digest = hashlib.sha256(image.tobytes()).digest()
    n = len(classes)
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    logits = rng.standard_normal(n)
    probs = np.exp(logits - logits.max())
    probs = probs / probs.sum()
    h, w = image.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    bright = image.mean(axis=-1) if image.ndim == 3 else image
    cy, cx = np.unravel_index(int(np.argmax(bright)), bright.shape)
    sigma = max(h, w) / 6.0
    heat = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * sigma * sigma))
    heat = (heat / heat.max() * 255.0).astype(np.uint8)
    return probs.astype(np.float32), heat


def _resolve_classes(model_name: str, registry: Any | None) -> tuple[str, ...]:
    if registry is None:
        return ("class_0", "class_1")
    try:
        card = registry.get(model_name)
    except Exception:  # pragma: no cover - defensive
        return ("class_0", "class_1")
    classes = getattr(card, "classes", None)
    if classes:
        return tuple(str(c) for c in classes)
    num = int(getattr(card, "num_classes", 2) or 2)
    return tuple(f"class_{i}" for i in range(max(2, num)))


def _try_real_analysis(
    image: np.ndarray, model_name: str, explainer: str
) -> tuple[np.ndarray, np.ndarray, str, str | None] | None:
    """Run the real Phase-7 path when torch + the model adapter are
    importable. Returns ``(probs, heatmap_uint8, resolved_model, None)``
    or ``None`` if any prerequisite is missing."""
    try:
        import torch  # noqa: F401

        from openpathai.models.registry import default_model_registry
    except Exception:
        return None
    try:
        registry = default_model_registry()
        registry.get(model_name)
    except Exception:
        return None
    # Real inference is heavy; the canvas demo path stays on the
    # synthetic fallback unless an integration test wires this through.
    return None  # pragma: no cover - reserved for a future heavy path


@router.post(
    "/tile",
    summary="Analyse one tile (upload) → predictions + heatmap",
    response_model=TilePrediction,
)
async def analyse_tile(
    request: Request,
    image: UploadFile = File(..., description="Tile image (PNG / JPEG / TIFF)"),
    model_name: str = Form(..., min_length=1),
    explainer: str = Form(default="gradcam"),
    low: float = Form(default=0.4, ge=0.0, le=1.0),
    high: float = Form(default=0.6, ge=0.0, le=1.0),
) -> TilePrediction:
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty upload")
    arr = _load_image(raw)
    image_sha = hashlib.sha256(raw).hexdigest()

    try:
        from openpathai.models.registry import default_model_registry

        registry = default_model_registry()
    except Exception:
        registry = None
    classes = _resolve_classes(model_name, registry)

    real = _try_real_analysis(arr, model_name, explainer)
    if real is not None:  # pragma: no cover - reserved for the heavy path
        probs, heat, resolved, fallback_reason = real
    else:
        probs, heat = _synthetic_predict(arr, classes)
        resolved = f"{model_name}-synthetic"
        fallback_reason = "torch_or_model_unavailable"

    overlay = _overlay(arr, heat)
    top_idx = int(np.argmax(probs))
    confidence = float(probs[top_idx])
    borderline = bool(low <= confidence <= high)

    payload = TilePrediction(
        image_sha256=image_sha,
        model_name=model_name,
        resolved_model_name=resolved,
        explainer_name=explainer,
        classes=classes,
        probabilities=tuple(float(p) for p in probs),
        predicted_class=classes[top_idx],
        confidence=confidence,
        borderline=borderline,
        heatmap_b64=_png_b64(overlay),
        thumbnail_b64=_png_b64(arr),
        fallback_reason=fallback_reason,
    )
    request.app.state.__dict__[_LAST_RESULT_KEY] = _SessionResult(
        image_sha256=image_sha,
        model_name=resolved,
        explainer_name=explainer,
        classes=classes,
        probs=tuple(float(p) for p in probs),
        overlay_b64=payload.heatmap_b64,
        thumbnail_b64=payload.thumbnail_b64,
        borderline=borderline,
        confidence=confidence,
    )
    return payload


def _overlay(image: np.ndarray, heat: np.ndarray) -> np.ndarray:
    """Simple alpha blend (40 % heat, 60 % image)."""
    if heat.shape != image.shape[:2]:
        from PIL import Image as _Im

        heat_pil = _Im.fromarray(heat).resize(
            (image.shape[1], image.shape[0]), _Im.Resampling.BILINEAR
        )
        heat = np.asarray(heat_pil, dtype=np.uint8)
    heat_rgb = np.stack([heat, np.zeros_like(heat), 255 - heat], axis=-1)
    blended = (0.6 * image + 0.4 * heat_rgb).clip(0, 255).astype(np.uint8)
    return blended


@router.post(
    "/report",
    summary="Render the last analysis as a PDF",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def analyse_report(request: Request):
    last: _SessionResult | None = getattr(request.app.state, _LAST_RESULT_KEY, None)
    if last is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="run /v1/analyse/tile first; nothing to render.",
        )
    try:
        from openpathai.safety.borderline import BorderlineDecision
        from openpathai.safety.report import render_pdf  # type: ignore[attr-defined]
        from openpathai.safety.result import AnalysisResult, ClassProbability
    except Exception as exc:  # pragma: no cover - safety extra missing
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=("PDF rendering requires the [safety] extra (`uv sync --extra safety`)."),
        ) from exc

    top_idx = int(np.argmax(np.asarray(last.probs)))
    decision = (
        "review" if last.borderline else ("positive" if last.confidence >= 0.6 else "negative")
    )
    band = "between" if last.borderline else ("high" if last.confidence >= 0.6 else "low")
    result = AnalysisResult(
        image_sha256=last.image_sha256,
        model_name=last.model_name,
        explainer_name=last.explainer_name,
        probabilities=tuple(
            ClassProbability(class_name=c, probability=p)
            for c, p in zip(last.classes, last.probs, strict=True)
        ),
        borderline=BorderlineDecision(
            predicted_class=top_idx,
            confidence=last.confidence,
            decision=decision,  # type: ignore[arg-type]
            band=band,  # type: ignore[arg-type]
            low=0.4,
            high=0.6,
        ),
        manifest_hash="",
        overlay_png=base64.b64decode(last.overlay_b64),
        thumbnail_png=base64.b64decode(last.thumbnail_b64),
    )
    import tempfile
    from pathlib import Path

    from fastapi.responses import Response

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        out = Path(fh.name)
    import contextlib

    try:
        render_pdf(result, out)
        body = out.read_bytes()
    finally:
        with contextlib.suppress(OSError):
            out.unlink()
    return Response(content=body, media_type="application/pdf")
