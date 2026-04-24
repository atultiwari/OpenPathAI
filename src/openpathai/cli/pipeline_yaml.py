"""YAML -> :class:`Pipeline` loader used by ``openpathai run``.

The on-disk format is intentionally the same shape as the pydantic
models ship: a top-level mapping with ``id``, optional ``mode``, and a
``steps`` list. Step inputs accept literal Python values as well as
``@step`` / ``@step.field`` references. Informative errors surface the
exact field path that failed to validate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from openpathai.pipeline.executor import Pipeline

__all__ = [
    "PipelineYamlError",
    "dump_pipeline",
    "load_pipeline",
    "loads_pipeline",
]


class PipelineYamlError(ValueError):
    """Raised when a pipeline YAML can't be parsed or validated."""


def _validate_payload(payload: Any, *, source: str) -> Pipeline:
    if not isinstance(payload, dict):
        raise PipelineYamlError(
            f"Pipeline YAML at {source} must be a mapping (got {type(payload).__name__})"
        )
    try:
        return Pipeline.model_validate(payload)
    except ValidationError as exc:
        raise PipelineYamlError(f"Invalid pipeline YAML at {source}: {exc}") from exc


def load_pipeline(path: str | Path) -> Pipeline:
    """Parse a YAML file into a :class:`Pipeline`."""
    p = Path(path)
    if not p.exists():
        raise PipelineYamlError(f"Pipeline YAML not found at {p}")
    try:
        payload = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PipelineYamlError(f"Could not parse YAML at {p}: {exc}") from exc
    return _validate_payload(payload, source=str(p))


def loads_pipeline(text: str) -> Pipeline:
    """Parse a YAML string into a :class:`Pipeline`.

    Symmetric companion to :func:`dump_pipeline`. Used by the Phase 11
    Colab exporter so the embedded pipeline YAML can be fed straight
    back through the loader during notebook rendering.
    """
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PipelineYamlError(f"Could not parse pipeline YAML: {exc}") from exc
    return _validate_payload(payload, source="<string>")


def dump_pipeline(pipeline: Pipeline) -> str:
    """Serialise a :class:`Pipeline` to a YAML string.

    Round-trips with :func:`load_pipeline` / :func:`loads_pipeline`
    modulo key ordering. Useful for the auto-generated Methods
    sections in Phase 17 and the Phase 11 Colab exporter.
    """
    payload: dict[str, Any] = pipeline.model_dump(mode="json")
    return yaml.safe_dump(payload, sort_keys=False)
