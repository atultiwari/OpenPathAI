"""Phase 11 master-plan acceptance — Colab export → parse → re-import.

Walks the full reproducibility round-trip end-to-end:

1. Generate a notebook via ``render_notebook`` for a real shipped
   pipeline YAML.
2. Parse the notebook (pure nbformat / JSON).
3. Assert the install cell pins ``openpathai``.
4. Assert the pipeline YAML round-trips through the ``%%writefile``
   cell without mutation.
5. Synthesize a :class:`RunManifest` as if the notebook had run on
   Colab, import it via ``openpathai sync``, and assert the local
   audit DB has a row that points back at the same pipeline.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app
from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.export import render_notebook, write_notebook
from openpathai.safety.audit import AuditDB

runner = CliRunner(mix_stderr=False)


def _shipped_yaml() -> Path:
    return Path(__file__).resolve().parents[2] / "pipelines" / "supervised_synthetic.yaml"


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))


def test_colab_export_then_sync_round_trip(tmp_path: Path) -> None:
    yaml_path = _shipped_yaml()
    pipeline = load_pipeline(yaml_path)

    nb = render_notebook(pipeline=pipeline, openpathai_version="0.1.0")
    out = write_notebook(nb, tmp_path / "run.ipynb")
    assert out.is_file()

    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["nbformat"] == 4

    # Install cell pins the version we asked for.
    install_src = "".join(parsed["cells"][1]["source"])
    assert '%pip install --quiet "openpathai==0.1.0"' in install_src

    # Pipeline YAML round-trips through the "write pipeline.yaml" cell verbatim.
    yaml_cell = next(
        cell
        for cell in parsed["cells"]
        if cell["cell_type"] == "code"
        and "pipeline_yaml =" in "".join(cell["source"])
        and "/content/pipeline.yaml" in "".join(cell["source"])
    )
    yaml_cell_src = "".join(yaml_cell["source"])
    # The embedded YAML is a Python string literal: `pipeline_yaml = "..."`.
    # Extract the literal safely via ast.literal_eval on the rhs.
    assignment_line = next(
        line for line in yaml_cell_src.splitlines() if line.startswith("pipeline_yaml = ")
    )
    embedded_yaml = ast.literal_eval(assignment_line.split("=", 1)[1].strip())
    # The embedded YAML is what `dump_pipeline` produced — it's semantically
    # equivalent to the source but may drop comments. Assert round-trip
    # parses back to the same Pipeline.
    from openpathai.cli.pipeline_yaml import loads_pipeline

    reloaded = loads_pipeline(embedded_yaml)
    assert reloaded.id == pipeline.id
    assert reloaded.graph_hash() == pipeline.graph_hash()

    # Now simulate the Colab run: synthesize a RunManifest that would
    # have been emitted by `openpathai run` and feed it to `sync`.
    manifest_payload = {
        "run_id": "colab-roundtrip-001",
        "pipeline_id": pipeline.id,
        "pipeline_graph_hash": "roundtrip-hash",
        "timestamp_start": "2026-04-15T10:00:00+00:00",
        "timestamp_end": "2026-04-15T10:00:30+00:00",
        "mode": "exploratory",
        "environment": {"git_commit": "colabfff", "tier": "colab"},
        "cache_stats": {"hits": 0, "misses": 3},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

    result = runner.invoke(app, ["sync", str(manifest_path)])
    assert result.exit_code == 0, result.stdout
    assert "Imported run colab-roundtrip-001" in result.stdout

    db = AuditDB.open_default()
    entry = db.get_run("colab-roundtrip-001")
    assert entry is not None
    assert entry.pipeline_yaml_hash == "roundtrip-hash"
    assert entry.tier == "colab"
    assert entry.git_commit == "colabfff"
    assert entry.status == "success"
