"""Unit tests for the YAML pipeline loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.cli.pipeline_yaml import (
    PipelineYamlError,
    dump_pipeline,
    load_pipeline,
)
from openpathai.pipeline.executor import Pipeline, PipelineStep


def _write(tmp_path: Path, body: str, *, name: str = "pipeline.yaml") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    target = tmp_path / name
    target.write_text(body, encoding="utf-8")
    return target


def test_load_pipeline_round_trip(tmp_path: Path) -> None:
    body = """
id: demo
mode: exploratory
steps:
  - id: a
    op: demo.constant
    inputs:
      value: 3
  - id: b
    op: demo.double
    inputs:
      value: "@a.value"
"""
    pipeline = load_pipeline(_write(tmp_path, body))
    assert pipeline.id == "demo"
    assert [s.id for s in pipeline.steps] == ["a", "b"]
    rendered = dump_pipeline(pipeline)
    # Re-parsing the rendered YAML yields an identical pipeline.
    redump = load_pipeline(_write(tmp_path / "redump", rendered))
    assert redump == pipeline


def test_load_pipeline_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PipelineYamlError, match="not found"):
        load_pipeline(tmp_path / "nope.yaml")


def test_load_pipeline_rejects_non_mapping(tmp_path: Path) -> None:
    with pytest.raises(PipelineYamlError, match="must be a mapping"):
        load_pipeline(_write(tmp_path, "- just\n- a list\n"))


def test_load_pipeline_rejects_malformed_yaml(tmp_path: Path) -> None:
    with pytest.raises(PipelineYamlError, match="Could not parse"):
        load_pipeline(_write(tmp_path, ":\n:::"))


def test_load_pipeline_rejects_bad_step(tmp_path: Path) -> None:
    body = """
id: demo
steps:
  - id: a
    op: demo.constant
    unknown_field: 42
"""
    with pytest.raises(PipelineYamlError, match="Invalid pipeline YAML"):
        load_pipeline(_write(tmp_path, body))


def test_dump_pipeline_matches_model_dump() -> None:
    pipeline = Pipeline(
        id="demo",
        steps=[PipelineStep(id="a", op="demo.constant", inputs={"value": 3})],
    )
    rendered = dump_pipeline(pipeline)
    assert "id: demo" in rendered
    assert "demo.constant" in rendered
