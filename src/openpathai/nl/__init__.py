"""OpenPathAI — natural-language + zero-shot surface (Phase 15).

Four subsystems, all library-first:

* :mod:`openpathai.nl.llm_backends` — `LLMBackend` protocol +
  Ollama + LM Studio + the OpenAI-chat-compatible HTTP adapter
  they share. :func:`detect_default_backend` probes each and
  returns the first reachable one.
* :mod:`openpathai.nl.zero_shot` — CONCH text-prompted tile
  classification. Falls back to a deterministic hash-based text
  encoder so the call path is exercisable on any CI cell
  (whether the user has gated CONCH access or not).
* :mod:`openpathai.nl.text_prompt_seg` — MedSAM2 text-prompted
  segmentation via CONCH's text encoder. Falls back to the
  Phase-14 :class:`SyntheticClickSegmenter` when real MedSAM2
  weights are unavailable.
* :mod:`openpathai.nl.pipeline_gen` — MedGemma-driven
  :class:`Pipeline` YAML drafting with a pydantic-validation
  retry loop.

Iron rule #9 holds here: we never auto-execute LLM-generated
pipelines. :func:`draft_pipeline_from_prompt` returns the
parsed :class:`Pipeline` for the user (or GUI) to review; running
it is always an explicit second step.
"""

from __future__ import annotations

from openpathai.nl.llm_backends.base import (
    BackendCapabilities,
    ChatMessage,
    ChatResponse,
    LLMBackend,
    LLMUnavailableError,
)
from openpathai.nl.llm_backends.lmstudio import LMStudioBackend
from openpathai.nl.llm_backends.ollama import OllamaBackend
from openpathai.nl.llm_backends.registry import (
    LLMBackendRegistry,
    default_llm_backend_registry,
    detect_default_backend,
)
from openpathai.nl.pipeline_gen import (
    PipelineDraft,
    PipelineDraftError,
    draft_pipeline_from_prompt,
)
from openpathai.nl.text_prompt_seg import segment_text_prompt
from openpathai.nl.zero_shot import (
    ZeroShotResult,
    classify_zero_shot,
)

__all__ = [
    "BackendCapabilities",
    "ChatMessage",
    "ChatResponse",
    "LLMBackend",
    "LLMBackendRegistry",
    "LLMUnavailableError",
    "LMStudioBackend",
    "OllamaBackend",
    "PipelineDraft",
    "PipelineDraftError",
    "ZeroShotResult",
    "classify_zero_shot",
    "default_llm_backend_registry",
    "detect_default_backend",
    "draft_pipeline_from_prompt",
    "segment_text_prompt",
]
