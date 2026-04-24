"""MedGemma-driven :class:`Pipeline` YAML drafting.

``draft_pipeline_from_prompt(prompt)`` asks the configured LLM
backend to produce a YAML string matching the Phase-5
``Pipeline`` schema, then validates via
:func:`openpathai.cli.pipeline_yaml.loads_pipeline`. On
validation failure, the last parser error is fed back into the
conversation and the model is asked to correct itself — up to
:data:`_MAX_ATTEMPTS` times.

Iron rule #9: we **never** auto-execute the drafted pipeline.
The returned :class:`PipelineDraft` carries the parsed
``Pipeline`` for the caller (or GUI) to inspect and then run
explicitly via ``openpathai run``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from openpathai.cli.pipeline_yaml import PipelineYamlError, loads_pipeline
from openpathai.nl.llm_backends.base import ChatMessage, LLMBackend

__all__ = [
    "SYSTEM_PROMPT",
    "PipelineDraft",
    "PipelineDraftError",
    "draft_pipeline_from_prompt",
]


_MAX_ATTEMPTS = 3


class PipelineDraftError(RuntimeError):
    """Raised when the LLM couldn't produce a valid pipeline YAML
    after :data:`_MAX_ATTEMPTS` attempts. The last raw LLM output
    is attached so the user can salvage it manually."""

    def __init__(self, message: str, *, last_output: str = "") -> None:
        super().__init__(message)
        self.last_output = last_output


class PipelineDraft(BaseModel):
    """One successful draft."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    prompt: str = Field(min_length=1)
    prompt_hash: str = Field(min_length=1)
    yaml_text: str = Field(min_length=1)
    pipeline: Any  # a validated openpathai.pipeline.executor.Pipeline
    backend_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    attempts: int = Field(ge=1)


SYSTEM_PROMPT = """\
You are a tool that drafts OpenPathAI pipeline YAMLs from short
natural-language descriptions. You MUST output a single YAML
document that round-trips through the following pydantic schema
(fields with defaults may be omitted; unknown top-level fields are
rejected):

Pipeline:
  id: str (alnum + '-' + '_')
  mode: 'exploratory' | 'diagnostic'   (default: 'exploratory')
  steps: list[PipelineStep]
  cohort_fanout: str (optional, a step id)
  max_workers: int (optional, >= 1)

PipelineStep:
  id: str (alnum + '-' + '_')
  op: str   (must reference a registered node id)
  inputs: mapping[str, Any]   (literals, or '@other_step' refs)

Rules:
- Output ONLY the YAML document. No markdown fences, no commentary.
- Do NOT add a top-level `description:` field — the schema forbids it.
- Use real registered op ids where possible (e.g. 'training.train'
  for the Phase-3 trainer). If unsure, use a placeholder op id and
  add an 'inputs.note' string explaining what the user should verify.
- Prefer exploratory mode unless the prompt mentions 'diagnostic'
  or 'reproducibility'.
- Keep the step count small (1-5) and the YAML under 80 lines.
"""


def draft_pipeline_from_prompt(
    prompt: str,
    *,
    backend: LLMBackend,
    temperature: float = 0.2,
) -> PipelineDraft:
    """Draft a :class:`Pipeline` YAML from ``prompt``."""
    if not prompt.strip():
        raise ValueError("prompt must be non-empty")
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ]
    last_output = ""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        response = backend.chat(messages, temperature=temperature)
        last_output = response.content.strip()
        yaml_text = _extract_yaml(last_output)
        try:
            pipeline = loads_pipeline(yaml_text)
        except PipelineYamlError as exc:
            # Feed the error back and ask for a correction.
            messages.extend(
                [
                    ChatMessage(role="assistant", content=last_output),
                    ChatMessage(
                        role="user",
                        content=(
                            f"Your previous response did not validate: {exc!s}\n"
                            "Produce a corrected YAML only."
                        ),
                    ),
                ]
            )
            continue
        return PipelineDraft(
            prompt=prompt,
            prompt_hash=prompt_hash,
            yaml_text=yaml_text,
            pipeline=pipeline,
            backend_id=response.backend_id,
            model_id=response.model_id,
            generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            attempts=attempt,
        )
    raise PipelineDraftError(
        f"Failed to draft a valid pipeline YAML after {_MAX_ATTEMPTS} attempts.",
        last_output=last_output,
    )


def _extract_yaml(text: str) -> str:
    """Strip common markdown fences; leave plain YAML alone."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Drop opening fence line (e.g. ```yaml).
        lines = lines[1:]
        # Drop trailing fence if present.
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped
