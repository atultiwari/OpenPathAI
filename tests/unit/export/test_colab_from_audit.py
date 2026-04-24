"""Phase 11 — render_notebook uses audit_entry.run_id as lineage."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.export import render_notebook
from openpathai.safety.audit import AuditDB


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))


def test_source_run_id_embedded(tmp_path: Path) -> None:
    db = AuditDB.open_path(tmp_path / "audit.db")
    entry = db.insert_run(
        kind="pipeline",
        pipeline_yaml_hash="abc",
        graph_hash="def",
        manifest_path="",
    )
    pipeline = load_pipeline(
        Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"
    )
    nb = render_notebook(pipeline=pipeline, audit_entry=entry)
    assert nb["metadata"]["openpathai"]["source_run_id"] == entry.run_id

    # The intro markdown cell should mention the source run id so the
    # user sees provenance without opening metadata.
    intro = "".join(nb["cells"][0]["source"])
    assert entry.run_id in intro


def test_no_audit_entry_gives_blank_source_run_id() -> None:
    pipeline = load_pipeline(
        Path(__file__).resolve().parents[3] / "pipelines" / "supervised_synthetic.yaml"
    )
    nb = render_notebook(pipeline=pipeline)
    assert nb["metadata"]["openpathai"]["source_run_id"] == ""
