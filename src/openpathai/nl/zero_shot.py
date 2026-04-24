"""CONCH zero-shot tile classification.

CONCH is a visual-language foundation model from MahmoodLab that
exposes both an image encoder and a text encoder. Zero-shot
classification in practice is:

1. Encode the input image → 512-D vector.
2. Encode each natural-language prompt → 512-D vector.
3. Cosine-similarity image ↔ prompts, softmax with a scaled
   temperature → per-prompt probabilities.

The real CONCH is gated (``MahmoodLab/CONCH`` on HF, registered
in Phase 13 as a stub). Phase 15 promotes the stub to a full
adapter **only** when the caller explicitly has gated access;
otherwise :func:`classify_zero_shot` wires in a deterministic
hash-based text encoder so the call path is exercisable in CI
and for license-clean demos.

Iron rule #11 is honoured: the returned :class:`ZeroShotResult`
records both the requested and resolved model ids; the audit row
carries both too.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ZeroShotResult",
    "classify_zero_shot",
]


class ZeroShotResult(BaseModel):
    """Output of one :func:`classify_zero_shot` call."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    prompts: tuple[str, ...]
    probs: tuple[float, ...]
    predicted_prompt: str = Field(min_length=1)
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    backbone_id: str = Field(min_length=1)
    resolved_backbone_id: str = Field(min_length=1)


def classify_zero_shot(
    image: Any,
    prompts: Sequence[str],
    *,
    adapter: Any = None,
    temperature: float = 100.0,
    backbone_id: str = "conch",
) -> ZeroShotResult:
    """Zero-shot classify ``image`` against ``prompts``.

    When ``adapter`` is supplied and exposes both ``.embed()`` and
    ``.embed_text()``, uses them. Otherwise falls back to the
    deterministic hash-based encoders so the call path stays
    usable on any CI cell.
    """
    if not prompts:
        raise ValueError("prompts must be non-empty")
    arr = np.asarray(image)
    if arr.ndim == 3 or arr.ndim == 2:
        h, w = int(arr.shape[0]), int(arr.shape[1])
    else:
        raise ValueError(f"image must be 2-D or 3-D; got shape {arr.shape}")

    image_vec, text_matrix, resolved_id = _encode_fallback(
        image, prompts, adapter=adapter, backbone_id=backbone_id
    )
    # Cosine similarity + scaled softmax.
    image_norm = image_vec / (np.linalg.norm(image_vec) + 1e-9)
    text_norms = text_matrix / (np.linalg.norm(text_matrix, axis=1, keepdims=True) + 1e-9)
    sim = text_norms @ image_norm
    scaled = sim * float(temperature)
    scaled -= scaled.max()
    exp = np.exp(scaled)
    probs = exp / exp.sum()

    best = int(np.argmax(probs))
    return ZeroShotResult(
        prompts=tuple(prompts),
        probs=tuple(float(p) for p in probs),
        predicted_prompt=prompts[best],
        image_width=w,
        image_height=h,
        backbone_id=backbone_id,
        resolved_backbone_id=resolved_id,
    )


def _encode_fallback(
    image: Any,
    prompts: Sequence[str],
    *,
    adapter: Any,
    backbone_id: str,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Return ``(image_vec, text_matrix, resolved_id)`` using the
    real CONCH adapter when available, otherwise the deterministic
    hash-based fallback."""
    if (
        adapter is not None and hasattr(adapter, "embed") and hasattr(adapter, "embed_text")
    ):  # pragma: no cover — only reached when a real CONCH adapter is wired
        try:
            image_vec = np.asarray(adapter.embed(image), dtype=np.float32).reshape(-1)
            text_matrix = np.asarray(adapter.embed_text(list(prompts)), dtype=np.float32)
            return image_vec, text_matrix, getattr(adapter, "id", backbone_id)
        except Exception:
            pass
    # Synthetic fallback — hash prompts + image summary into 512-D.
    image_vec = _hash_image_vec(image, dim=512)
    text_matrix = np.stack([_hash_text_vec(p, dim=512) for p in prompts], axis=0)
    return image_vec, text_matrix, "synthetic_text_encoder"


def _hash_image_vec(image: Any, *, dim: int) -> np.ndarray:
    arr = np.asarray(image)
    digest = hashlib.sha256(arr.tobytes()).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    return rng.standard_normal(dim).astype(np.float32)


def _hash_text_vec(text: str, *, dim: int) -> np.ndarray:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    return rng.standard_normal(dim).astype(np.float32)
