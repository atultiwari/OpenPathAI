"""Zero-shot classify with the synthetic text-encoder fallback."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.nl import ZeroShotResult, classify_zero_shot


def _tile(size: int = 64, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.random((size, size, 3)) * 255).astype(np.uint8)


def test_classify_returns_valid_result() -> None:
    result = classify_zero_shot(_tile(), prompts=["tumor", "normal", "stroma"])
    assert isinstance(result, ZeroShotResult)
    assert result.prompts == ("tumor", "normal", "stroma")
    assert len(result.probs) == 3
    assert abs(sum(result.probs) - 1.0) < 1e-6
    assert all(0.0 <= p <= 1.0 for p in result.probs)
    assert result.predicted_prompt in result.prompts
    assert result.backbone_id == "conch"
    # Fallback routing records the synthetic resolved id.
    assert result.resolved_backbone_id == "synthetic_text_encoder"


def test_classify_is_deterministic() -> None:
    image = _tile(seed=7)
    a = classify_zero_shot(image, prompts=["tumor", "normal"])
    b = classify_zero_shot(image, prompts=["tumor", "normal"])
    assert a.probs == b.probs
    assert a.predicted_prompt == b.predicted_prompt


def test_classify_image_dimensions_propagate() -> None:
    result = classify_zero_shot(_tile(size=96), prompts=["a", "b"])
    assert result.image_width == 96
    assert result.image_height == 96


def test_classify_rejects_empty_prompts() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        classify_zero_shot(_tile(), prompts=[])


def test_classify_rejects_bad_image() -> None:
    with pytest.raises(ValueError, match="2-D or 3-D"):
        classify_zero_shot(np.zeros(4, dtype=np.uint8), prompts=["a", "b"])


def test_classify_temperature_affects_confidence() -> None:
    """Higher temperature → sharper softmax → higher max-prob."""
    image = _tile(seed=1)
    loose = classify_zero_shot(image, prompts=["a", "b"], temperature=10.0)
    tight = classify_zero_shot(image, prompts=["a", "b"], temperature=500.0)
    assert max(tight.probs) >= max(loose.probs)


def test_classify_two_prompts_partition() -> None:
    image = _tile(seed=3)
    result = classify_zero_shot(image, prompts=["cat", "dog"])
    # Binary-case probs still sum to 1 and pick one of the two prompts.
    assert len(result.probs) == 2
    assert result.predicted_prompt in ("cat", "dog")
