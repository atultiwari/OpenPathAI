"""Natural-language primitives (Phase 19).

Three endpoints:

- ``POST /v1/nl/draft-pipeline`` — MedGemma-drafted YAML; never
  runs it (iron rule #9). Echoes back the drafted YAML + prompt
  hash only — raw prompt never persisted or returned.
- ``POST /v1/nl/classify`` — CONCH zero-shot on a base64-encoded
  tile. Returns probabilities per prompt.
- ``POST /v1/nl/segment`` — MedSAM2 text-prompt mask. Returns the
  mask as a run-length-encoded payload so the response is not
  gigantic.

Every endpoint validates the request body via pydantic + catches
LLMUnavailableError into a 503 so the React canvas can render a
friendly "install Ollama" banner.
"""

from __future__ import annotations

import base64
import binascii
from io import BytesIO
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, status
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from openpathai.server.auth import AuthDependency

__all__ = ["router"]


router = APIRouter(
    prefix="/nl",
    tags=["nl"],
    dependencies=[AuthDependency],
)


class DraftPipelineRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    model: str | None = None


class ClassifyRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    image_b64: str = Field(min_length=8)
    prompts: tuple[str, ...] = Field(min_length=1)


class SegmentRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    image_b64: str = Field(min_length=8)
    prompt: str = Field(min_length=1, max_length=512)


def _decode_image(image_b64: str) -> np.ndarray:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="image_b64 is not valid base64",
        ) from exc
    try:
        with Image.open(BytesIO(raw)) as pil:
            pil = pil.convert("RGB")
            return np.asarray(pil, dtype=np.uint8)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"could not decode image: {exc!s}",
        ) from exc


@router.post("/draft-pipeline", summary="Draft a pipeline YAML from a natural-language prompt")
async def draft_pipeline(body: DraftPipelineRequest) -> dict[str, Any]:
    from openpathai.nl import (
        LLMUnavailableError,
        PipelineDraftError,
        default_llm_backend_registry,
        detect_default_backend,
        draft_pipeline_from_prompt,
    )

    try:
        backend = detect_default_backend(registry=default_llm_backend_registry())
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if body.model is not None:
        backend.model = body.model  # type: ignore[misc]
    try:
        draft = draft_pipeline_from_prompt(body.prompt, backend=backend)
    except PipelineDraftError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"pipeline draft failed: {exc!s}",
        ) from exc
    return {
        # Iron rule #8 — never return the raw prompt.
        "prompt_hash": draft.prompt_hash,
        "backend_id": draft.backend_id,
        "model_id": draft.model_id,
        "generated_at": draft.generated_at,
        "attempts": draft.attempts,
        "pipeline_id": draft.pipeline.id,
        "yaml": draft.yaml_text,
        "pipeline": draft.pipeline.model_dump(mode="json"),
    }


@router.post("/classify", summary="CONCH zero-shot tile classification")
async def classify(body: ClassifyRequest) -> dict[str, Any]:
    from openpathai.nl.zero_shot import classify_zero_shot

    image = _decode_image(body.image_b64)
    result = classify_zero_shot(image, list(body.prompts))
    return result.model_dump(mode="json")


@router.post("/segment", summary="MedSAM2 text-prompted segmentation")
async def segment(body: SegmentRequest) -> dict[str, Any]:
    from openpathai.nl.text_prompt_seg import segment_text_prompt

    image = _decode_image(body.image_b64)
    result = segment_text_prompt(image, body.prompt)
    mask_arr = np.asarray(result.mask.array, dtype=np.int32)
    flat = mask_arr.reshape(-1)
    # Lightweight RLE so the wire payload stays small for typical
    # mostly-background masks.
    rle: list[list[int]] = []
    if flat.size:
        prev = int(flat[0])
        count = 1
        for val in flat[1:]:
            v = int(val)
            if v == prev:
                count += 1
            else:
                rle.append([prev, count])
                prev = v
                count = 1
        rle.append([prev, count])
    return {
        "image_width": result.image_width,
        "image_height": result.image_height,
        "model_id": result.model_id,
        "resolved_model_id": result.resolved_model_id,
        "mask_shape": list(mask_arr.shape),
        "mask_rle": rle,
        "class_names": list(result.mask.class_names),
        "metadata": dict(result.metadata),
    }
