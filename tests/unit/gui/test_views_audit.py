"""GUI view-model helpers for the Phase 8 Runs tab."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.gui.views import (
    audit_detail,
    audit_rows,
    audit_summary,
    run_diff_rows,
)
from openpathai.safety.audit import AuditDB


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path))


def _seed_runs() -> tuple[str, str]:
    db = AuditDB.open_default()
    a = db.insert_run(
        kind="training",
        pipeline_yaml_hash="p-a",
        graph_hash="g-a",
        git_commit="aaa",
        metrics={"acc": 0.8},
        manifest_path="",
    )
    b = db.insert_run(
        kind="pipeline",
        pipeline_yaml_hash="p-b",
        graph_hash="g-b",
        git_commit="bbb",
        metrics={"steps": 5},
        manifest_path="",
    )
    return a.run_id, b.run_id


def test_audit_rows_shapes() -> None:
    _seed_runs()
    rows = audit_rows()
    assert rows
    expected_keys = {
        "run_id",
        "kind",
        "mode",
        "status",
        "timestamp_start",
        "timestamp_end",
        "tier",
        "git_commit",
        "pipeline_yaml_hash",
    }
    for row in rows:
        assert expected_keys.issubset(row.keys())


def test_audit_rows_filter_by_kind() -> None:
    _seed_runs()
    training = audit_rows(kind="training")
    assert {r["kind"] for r in training} == {"training"}


def test_audit_detail_known_run() -> None:
    run_a, _ = _seed_runs()
    detail = audit_detail(run_a)
    assert detail["run"]["run_id"] == run_a
    assert isinstance(detail["analyses"], list)


def test_audit_detail_unknown_run_returns_empty() -> None:
    assert audit_detail("does-not-exist") == {}


def test_audit_summary_has_token_field() -> None:
    _seed_runs()
    summary = audit_summary()
    assert "token" in summary
    assert "runs" in summary
    assert summary["runs"] >= 2


def test_run_diff_rows_happy_path() -> None:
    run_a, run_b = _seed_runs()
    rows = run_diff_rows(run_a, run_b)
    assert rows
    for row in rows:
        assert len(row) == 4
        assert row[1] in {"added", "removed", "changed"}


def test_run_diff_rows_missing_returns_empty() -> None:
    assert run_diff_rows("missing-a", "missing-b") == []
