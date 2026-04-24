"""Phase 16 — NL view-model helpers (zero-shot + draft)."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.gui.views import (
    nl_classify_for_gui,
    nl_draft_pipeline_for_gui,
)


def _tile(size: int = 64, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.random((size, size, 3)) * 255).astype(np.uint8)


def test_nl_classify_sorts_probs_descending() -> None:
    rows = nl_classify_for_gui(_tile(), prompt_csv="tumor, normal, stroma")
    assert len(rows) == 3
    probs = [r[1] for r in rows]
    assert probs == sorted(probs, reverse=True)
    assert abs(sum(probs) - 1.0) < 1e-6
    assert {r[0] for r in rows} == {"tumor", "normal", "stroma"}


def test_nl_classify_rejects_single_prompt() -> None:
    with pytest.raises(ValueError, match="two"):
        nl_classify_for_gui(_tile(), prompt_csv="tumor")


def test_nl_classify_rejects_empty_csv() -> None:
    with pytest.raises(ValueError, match="two"):
        nl_classify_for_gui(_tile(), prompt_csv=", ,")


def test_nl_draft_returns_error_when_no_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CI cells don't have Ollama / LM Studio running → helper returns
    ``{"error": "..."}`` instead of raising."""
    monkeypatch.delenv("HF_TOKEN", raising=False)
    result = nl_draft_pipeline_for_gui("fine-tune resnet18 on lc25000")
    assert "error" in result
    assert "No LLM backend" in str(result["error"]) or "backend" in str(result["error"]).lower()


def test_nl_draft_rejects_empty_prompt() -> None:
    result = nl_draft_pipeline_for_gui("   ")
    assert result == {"error": "prompt must be non-empty"}
