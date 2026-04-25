"""Phase 21.5 chunk D — quickstart pipeline yaml validates + topo-sorts."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.cli.pipeline_yaml import PipelineYamlError, load_pipeline

REPO_ROOT = Path(__file__).resolve().parents[3]
QUICKSTART_YAML = REPO_ROOT / "pipelines" / "quickstart_pcam_dinov2.yaml"


def test_quickstart_yaml_exists() -> None:
    assert QUICKSTART_YAML.is_file(), (
        f"Phase 21.5 chunk D quickstart yaml must ship at {QUICKSTART_YAML.relative_to(REPO_ROOT)}"
    )


def test_quickstart_yaml_loads_and_validates() -> None:
    pipeline = load_pipeline(QUICKSTART_YAML)
    assert pipeline.id == "quickstart-pcam-dinov2"
    assert pipeline.mode == "exploratory"
    assert len(pipeline.steps) == 3
    step_ids = [s.id for s in pipeline.steps]
    assert step_ids == [
        "dataset_slice_id",
        "feature_batch_count",
        "linear_probe_metric",
    ]


def test_quickstart_yaml_uses_only_registered_ops() -> None:
    """Iron rule: never ship a yaml that references ops the live
    registry doesn't know about — a fresh laptop opens it on day one."""
    # Trigger registration of the demo ops.
    import openpathai.demo  # noqa: F401
    from openpathai.pipeline.node import REGISTRY as NODE_REGISTRY

    pipeline = load_pipeline(QUICKSTART_YAML)
    known = set(NODE_REGISTRY.all().keys())
    used = {step.op for step in pipeline.steps}
    missing = used - known
    assert not missing, (
        f"quickstart yaml references unregistered ops: {sorted(missing)}; "
        "either register them or guard the yaml behind a Phase-22 marker."
    )


def test_quickstart_yaml_chained_references_resolve() -> None:
    """The mean step references both upstream values — make sure the
    @step.field syntax round-trips through the loader."""
    pipeline = load_pipeline(QUICKSTART_YAML)
    mean_step = next(s for s in pipeline.steps if s.id == "linear_probe_metric")
    assert mean_step.inputs["a"] == "@dataset_slice_id.value"
    assert mean_step.inputs["b"] == "@feature_batch_count.value"


def test_quickstart_yaml_loader_raises_on_unknown_path() -> None:
    """Sanity check on the loader's error path — keeps this test file
    honest about negative cases too."""
    with pytest.raises(PipelineYamlError):
        load_pipeline(REPO_ROOT / "pipelines" / "definitely-not-here.yaml")
