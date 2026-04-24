"""Phase 11 — ``openpathai.export.render_notebook`` contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openpathai import __version__ as openpathai_version
from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.export import ColabExportError, render_notebook, write_notebook


def _pipeline():
    return load_pipeline(
        Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"
    )


def test_render_notebook_valid_ipynb_shape() -> None:
    nb = render_notebook(pipeline=_pipeline())
    assert nb["nbformat"] == 4
    assert nb["cells"], "expected at least one cell"
    # First cell is the markdown intro.
    assert nb["cells"][0]["cell_type"] == "markdown"
    # JSON-serialisable round-trip.
    blob = json.dumps(nb)
    reloaded = json.loads(blob)
    assert reloaded == nb


def test_render_notebook_pins_install_version() -> None:
    nb = render_notebook(pipeline=_pipeline())
    install_cell_sources = [
        s
        for cell in nb["cells"]
        if cell["cell_type"] == "code"
        for s in cell["source"]
        if "openpathai==" in s
    ]
    assert install_cell_sources
    assert f"openpathai=={openpathai_version}" in "".join(install_cell_sources)


def test_render_notebook_embeds_pipeline_yaml() -> None:
    pipeline = _pipeline()
    nb = render_notebook(pipeline=pipeline)
    yaml_cell = next(
        cell
        for cell in nb["cells"]
        if cell["cell_type"] == "code"
        and any("pipeline_yaml = " in line for line in cell["source"])
    )
    joined = "".join(yaml_cell["source"])
    assert "pipeline_yaml = " in joined
    # The step ids should all appear in the embedded YAML.
    for step in pipeline.steps:
        assert step.id in joined


def test_render_notebook_contains_openpathai_run() -> None:
    nb = render_notebook(pipeline=_pipeline())
    # Find the code cell that invokes `openpathai run`, then flatten its
    # entire source so multi-line shell continuations (`--no-audit` on
    # the last line) are included.
    run_cell_sources = [
        "".join(cell["source"])
        for cell in nb["cells"]
        if cell["cell_type"] == "code" and "openpathai run" in "".join(cell["source"])
    ]
    assert run_cell_sources, "expected a code cell invoking openpathai run"
    joined = "\n".join(run_cell_sources)
    assert "openpathai run /content/pipeline.yaml" in joined
    assert "--no-audit" in joined


def test_render_notebook_contains_download_helper() -> None:
    nb = render_notebook(pipeline=_pipeline())
    sources = "".join(
        s for cell in nb["cells"] if cell["cell_type"] == "code" for s in cell["source"]
    )
    assert "google.colab.files.download" not in sources
    assert "from google.colab import files" in sources
    assert "files.download('/content/run/manifest.json')" in sources


def test_render_notebook_metadata_has_pipeline_graph_hash() -> None:
    pipeline = _pipeline()
    nb = render_notebook(pipeline=pipeline)
    meta = nb["metadata"]["openpathai"]
    assert meta["pipeline_id"] == pipeline.id
    assert meta["pipeline_graph_hash"] == pipeline.graph_hash()
    assert meta["openpathai_version"] == openpathai_version
    assert meta["pip_spec"] == f"openpathai=={openpathai_version}"


def test_render_notebook_version_override() -> None:
    nb = render_notebook(pipeline=_pipeline(), openpathai_version="1.2.3")
    assert nb["metadata"]["openpathai"]["openpathai_version"] == "1.2.3"
    assert nb["metadata"]["openpathai"]["pip_spec"] == "openpathai==1.2.3"


def test_render_notebook_requires_source() -> None:
    with pytest.raises(ColabExportError, match="pipeline"):
        render_notebook()


def test_render_notebook_accepts_yaml_string() -> None:
    from openpathai.cli.pipeline_yaml import dump_pipeline

    yaml_text = dump_pipeline(_pipeline())
    nb = render_notebook(pipeline_yaml=yaml_text)
    assert nb["cells"], "yaml-only path must still produce cells"


def test_write_notebook_round_trip(tmp_path: Path) -> None:
    nb = render_notebook(pipeline=_pipeline())
    out = write_notebook(nb, tmp_path / "r.ipynb")
    assert out.exists()
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    assert reloaded == nb
