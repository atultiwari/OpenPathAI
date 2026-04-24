"""diff_runs + diff_dicts."""

from __future__ import annotations

from openpathai.safety.audit import AuditEntry, diff_runs
from openpathai.safety.audit.diff import diff_dicts


def _entry(**overrides) -> AuditEntry:
    defaults: dict = {
        "run_id": "r-a",
        "kind": "pipeline",
        "mode": "exploratory",
        "timestamp_start": "2026-04-24T00:00:00+00:00",
        "timestamp_end": "2026-04-24T00:01:00+00:00",
        "pipeline_yaml_hash": "p-1",
        "graph_hash": "g-1",
        "git_commit": "deadbeef",
        "tier": "T1",
        "status": "success",
        "metrics_json": '{"acc": 0.9}',
        "manifest_path": "/tmp/a",
    }
    defaults.update(overrides)
    return AuditEntry(**defaults)


def test_identical_runs_have_empty_diff() -> None:
    a = _entry()
    b = _entry()
    result = diff_runs(a, b)
    assert result.is_empty()
    assert result.deltas == ()


def test_scalar_delta_detected() -> None:
    a = _entry(status="success")
    b = _entry(run_id="r-b", status="failed")
    result = diff_runs(a, b)
    statuses = [d for d in result.deltas if d.field == "status"]
    assert len(statuses) == 1
    assert statuses[0].before == "success"
    assert statuses[0].after == "failed"
    assert statuses[0].kind == "changed"


def test_metrics_json_cracked_open() -> None:
    a = _entry(metrics_json='{"acc": 0.8, "ece": 0.05}')
    b = _entry(run_id="r-b", metrics_json='{"acc": 0.9, "ece": 0.05, "new": 1}')
    result = diff_runs(a, b)
    acc = [d for d in result.deltas if d.field == "metrics_json.acc"]
    assert len(acc) == 1
    assert acc[0].before == 0.8
    assert acc[0].after == 0.9
    new = [d for d in result.deltas if d.field == "metrics_json.new"]
    assert len(new) == 1
    assert new[0].kind == "added"


def test_unchanged_only_surfaced_when_requested() -> None:
    a = _entry()
    b = _entry(run_id="r-b", status="failed")
    without = diff_runs(a, b)
    with_uc = diff_runs(a, b, include_unchanged=True)
    assert without.unchanged == ()
    assert "timestamp_start" in with_uc.unchanged
    assert "metrics_json.acc" in with_uc.unchanged


def test_diff_dicts_all_kinds() -> None:
    deltas = diff_dicts({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 99, "d": 4})
    kinds = {d.field: d.kind for d in deltas}
    assert kinds["b"] == "changed"
    assert kinds["c"] == "removed"
    assert kinds["d"] == "added"
    assert "a" not in kinds  # unchanged, not emitted


def test_diff_dicts_handles_none() -> None:
    deltas = diff_dicts(None, {"a": 1})
    assert [d.kind for d in deltas] == ["added"]
