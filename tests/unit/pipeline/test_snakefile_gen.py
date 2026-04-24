"""Phase 10 — Snakefile exporter."""

from __future__ import annotations

from pathlib import Path

from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.pipeline.snakemake import generate_snakefile, write_snakefile


def _synthetic():
    return load_pipeline(
        Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"
    )


def test_generate_snakefile_has_one_rule_per_step() -> None:
    pipeline = _synthetic()
    text = generate_snakefile(pipeline)
    # One 'rule X:' line per step plus the top-level 'rule all:'.
    rule_count = sum(
        1 for line in text.splitlines() if line.startswith("rule ") and line.endswith(":")
    )
    assert rule_count == len(pipeline.steps) + 1


def test_generate_snakefile_contains_graph_hash() -> None:
    pipeline = _synthetic()
    text = generate_snakefile(pipeline)
    assert pipeline.graph_hash() in text


def test_generate_snakefile_cohort_fanout_has_expand_and_slides() -> None:
    pipeline = _synthetic()
    pipeline = pipeline.model_copy(update={"cohort_fanout": pipeline.steps[0].id})
    text = generate_snakefile(pipeline)
    assert "SLIDES" in text
    assert "expand(" in text
    assert "wildcards.slide_id" in text


def test_write_snakefile_round_trip(tmp_path: Path) -> None:
    pipeline = _synthetic()
    out = tmp_path / "demo.smk"
    written = write_snakefile(pipeline, out)
    assert written == out
    assert out.read_text(encoding="utf-8") == generate_snakefile(pipeline)


def test_generate_snakefile_dependencies_listed() -> None:
    """A step that @references another step should list it as input."""
    pipeline = _synthetic()
    text = generate_snakefile(pipeline)
    # 'doubled' references '@source.value' → rule doubled depends on source.done
    assert "rule doubled:" in text
    # The rule block for doubled should contain source.done as an input.
    blocks = text.split("rule ")
    doubled = next(b for b in blocks if b.startswith("doubled:"))
    assert "'source.done'" in doubled
